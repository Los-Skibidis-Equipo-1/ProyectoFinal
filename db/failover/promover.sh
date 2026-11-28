#!/usr/bin/env bash
# =====================================================================
# A12 · promover.sh <nodo_caido>
# Failover MANUAL de una región (D-01 §3 y §8). Se corre desde el nodo que
# tiene la copia del caído (o cualquier equipo que llegue a los nodos).
#
#   1. Comprueba que el nodo de verdad está caído: 2 de 3 nodos deben
#      verlo caído, en 3 revisiones seguidas (no se promueve por un corte
#      de un segundo).
#        - vista 1: desde aquí, pg_isready al nodo no responde;
#        - vista 2: en el tercer nodo, el caído ya no tiene conexiones de
#          replicación abiertas (no está leyendo de él).
#   2. En la copia: desactiva la suscripción que venía del caído (para
#      que, si regresa, no le mande nada) y agrega la región del caído a
#      app.region_local: desde ese momento RLS deja a la API escribir ahí.
#   3. Cierra las sesiones de la API en la copia para que reconecten con
#      el valor nuevo, y publica la región promovida para cuando el
#      caído regrese (reincorporar.sh).
#
# NO promueve si el caído es el escritor de las globales: eso es otro
# procedimiento (D-01 §10).
#
# Ejemplo (laboratorio): docker exec -e ... pg-sur bash /tmp/db/failover/promover.sh centro
# Responsable: Alexa Yalee Sánchez Tejeda · IA: generado y revisado (Claude)
# =====================================================================
source "$(dirname "$0")/_comun.sh"

CAIDO="${1:-}"; validar_nodo "$CAIDO"
REGION=$(region_de "$CAIDO")
COPIA=$(copia_de "$CAIDO")
TERCERO=$(tercero_de "$CAIDO")
SUB_DEL_CAIDO="sub_frag_r$REGION"
SUBS_DEL_CAIDO="'sub_frag_r$(region_copiada_por "$CAIDO")','sub_fijos_$CAIDO','sub_glob_$CAIDO'"

registro "=== Promoción: el nodo '$CAIDO' (región $REGION) se reporta caído ==="
registro "Su copia está en '$COPIA'; el tercer nodo es '$TERCERO'."

[ "$CAIDO" = "$ESCRITOR_GLOBALES" ] && \
    fallar "'$CAIDO' es el escritor de las tablas globales: sigue el procedimiento manual de D-01 §10."

vivo "$COPIA"   || fallar "la copia '$COPIA' tampoco responde: no hay a dónde promover."
vivo "$TERCERO" || fallar "el tercer nodo '$TERCERO' no responde: sin él no hay mayoría (2 de 3)."

# Si la región ya está promovida, no se hace nada.
YA=$(sql_en "$COPIA" "SELECT $REGION = ANY (app.fn_region_local())")
[ "$YA" = "t" ] && { registro "La región $REGION ya la atiende '$COPIA'. Nada que hacer."; exit 0; }

# ---------------------------------------------------------------------
# 1. Quórum: 3 revisiones, cada 5 s; en todas, las 2 vistas deben verlo caído.
# ---------------------------------------------------------------------
for ronda in 1 2 3; do
    if vivo "$CAIDO"; then
        fallar "ronda $ronda: '$CAIDO' SÍ responde desde aquí. No se promueve."
    fi
    CONEXIONES=$(sql_en "$TERCERO" \
        "SELECT count(*) FROM pg_stat_replication WHERE application_name IN ($SUBS_DEL_CAIDO)")
    if [ "$CONEXIONES" != "0" ]; then
        fallar "ronda $ronda: '$TERCERO' todavía ve a '$CAIDO' replicando ($CONEXIONES conexiones). No se promueve."
    fi
    registro "Ronda $ronda/3: '$CAIDO' no responde desde aquí y '$TERCERO' no lo ve conectado."
    [ "$ronda" -lt 3 ] && sleep 5
done
registro "Quórum: 2 de 3 nodos ven caído a '$CAIDO'."

# ---------------------------------------------------------------------
# 2. Promoción en la copia.
# ---------------------------------------------------------------------
ANTES=$(sql_en "$COPIA" "SELECT array_to_string(app.fn_region_local(), ',')")
NUEVO="$ANTES,$REGION"

sql_en "$COPIA" "ALTER SUBSCRIPTION $SUB_DEL_CAIDO DISABLE" >/dev/null
sql_en "$COPIA" "ALTER DATABASE plantas SET app.region_local = '$NUEVO'" >/dev/null
registro "En '$COPIA': suscripción $SUB_DEL_CAIDO desactivada; app.region_local '$ANTES' -> '$NUEVO'."

# Publicación de la región promovida (la usará reincorporar.sh).
LISTA=$(printf "app.%s_r$REGION, " "${TABLAS_FRAGMENTO[@]}"); LISTA=${LISTA%, }
sql_en "$COPIA" "DROP PUBLICATION IF EXISTS pub_promovida_r$REGION" >/dev/null
sql_en "$COPIA" "CREATE PUBLICATION pub_promovida_r$REGION FOR TABLE $LISTA" >/dev/null

# Las sesiones de la API reconectan y toman el valor nuevo.
CERRADAS=$(sql_en "$COPIA" "SELECT count(pg_terminate_backend(pid)) FROM pg_stat_activity
                            WHERE usename = 'plantas_api' AND datname = 'plantas'")
registro "Sesiones de la API cerradas en '$COPIA' para que reconecten: $CERRADAS."

registro "=== Listo: la región $REGION ahora la atiende '$COPIA'. ==="
registro "Siguiente paso: en la API, marcar la región $REGION -> nodo '$COPIA'."
registro "Cuando '$CAIDO' regrese: reincorporar.sh $CAIDO (se queda como copia)."
