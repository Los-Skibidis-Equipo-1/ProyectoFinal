#!/usr/bin/env bash
# =====================================================================
# A12 · reincorporar.sh <nodo_que_regresa>
# El nodo que se cayó (o quedó aislado) vuelve al anillo como COPIA de
# su antigua región (D-01 §3). Se corre cuando el nodo ya responde.
#
#   1. Protege al nodo: ya no atiende ninguna región (app.region_local
#      vacío, RLS bloquea a la API) y las sesiones de la API ahí son de
#      solo lectura (default_transaction_read_only, D-01 §8).
#   2. Quita la suscripción vieja de la copia hacia el nodo y la
#      publicación de su región (ya no es primario).
#   3. Descarta su partición de esa región: lo que escribió y no alcanzó
#      a replicarse (o escribió estando aislado) se pierde; es el RPO
#      declarado en D-01 §8. Informa cuántas filas se descartan.
#   4. Se suscribe al nuevo primario y copia la región completa.
#   5. Espera a terminar y compara el conteo de filas con el primario.
#
# Volver a ser primario de su región es un cambio PLANEADO, no lo hace
# este script (D-01 §3).
#
# Ejemplo (laboratorio): docker exec -e ... pg-sur bash /tmp/db/failover/reincorporar.sh centro
# Responsable: Alexa Yalee Sánchez Tejeda · IA: generado y revisado (Claude)
# =====================================================================
source "$(dirname "$0")/_comun.sh"

NODO="${1:-}"; validar_nodo "$NODO"
REGION=$(region_de "$NODO")
PRIMARIO=$(copia_de "$NODO")        # su antigua copia, hoy primario de la región
SUB_VIEJA="sub_frag_r$REGION"
SUB_NUEVA="sub_promovida_r$REGION"

registro "=== Reincorporación: '$NODO' (región $REGION) regresa como copia de '$PRIMARIO' ==="

vivo "$NODO"     || fallar "'$NODO' todavía no responde."
vivo "$PRIMARIO" || fallar "el primario actual '$PRIMARIO' no responde."
PROMOVIDA=$(sql_en "$PRIMARIO" "SELECT $REGION = ANY (app.fn_region_local())")
[ "$PROMOVIDA" = "t" ] || fallar "la región $REGION no fue promovida en '$PRIMARIO' (no hubo promover.sh)."

# ---------------------------------------------------------------------
# 1. Proteger al nodo que regresa.
# ---------------------------------------------------------------------
sql_en "$NODO" "ALTER DATABASE plantas SET app.region_local = ''" >/dev/null
sql_en "$NODO" "ALTER ROLE plantas_api IN DATABASE plantas SET default_transaction_read_only = on" >/dev/null
sql_en "$NODO" "SELECT count(pg_terminate_backend(pid)) FROM pg_stat_activity
                WHERE usename = 'plantas_api' AND datname = 'plantas'" >/dev/null
registro "En '$NODO': ya no atiende regiones y la API ahí es de solo lectura."

# ---------------------------------------------------------------------
# 2. Quitar la relación vieja (primario -> copia) en ambos lados.
# ---------------------------------------------------------------------
EXISTE=$(sql_en "$PRIMARIO" "SELECT count(*) FROM pg_subscription WHERE subname = '$SUB_VIEJA'")
if [ "$EXISTE" = "1" ]; then
    sql_en "$PRIMARIO" "ALTER SUBSCRIPTION $SUB_VIEJA DISABLE" >/dev/null
    sql_en "$PRIMARIO" "DROP SUBSCRIPTION $SUB_VIEJA" >/dev/null   # borra también su slot en el nodo
fi
sql_en "$NODO" "DROP PUBLICATION IF EXISTS pub_frag" >/dev/null
registro "Suscripción vieja $SUB_VIEJA quitada de '$PRIMARIO' y publicación pub_frag quitada de '$NODO'."

# ---------------------------------------------------------------------
# 3. Descartar la partición local de la región.
# ---------------------------------------------------------------------
DESCARTE=$(sql_en "$NODO" "SELECT
    (SELECT count(*) FROM app.usuario_r$REGION) || ' usuarios, ' ||
    (SELECT count(*) FROM app.planta_r$REGION)  || ' plantas, '  ||
    (SELECT count(*) FROM app.cuidado_r$REGION) || ' cuidados'")
BORRAR=""
for t in alerta cuidado sensor planta usuario; do BORRAR+="DELETE FROM app.${t}_r$REGION; "; done
psql "host=$(host_de "$NODO") port=$(port_de "$NODO") dbname=plantas user=postgres" -X -q -v ON_ERROR_STOP=1 \
     -c "BEGIN; SET LOCAL session_replication_role = replica; $BORRAR COMMIT;" >/dev/null
registro "En '$NODO' se descartó su copia local de la región $REGION ($DESCARTE); se vuelve a copiar del primario."

# ---------------------------------------------------------------------
# 4. Suscribirse al primario actual.
# ---------------------------------------------------------------------
sql_en "$NODO" "DROP SUBSCRIPTION IF EXISTS $SUB_NUEVA" >/dev/null
psql "host=$(host_de "$NODO") port=$(port_de "$NODO") dbname=plantas user=postgres" -X -q -v ON_ERROR_STOP=1 \
     -c "CREATE SUBSCRIPTION $SUB_NUEVA CONNECTION '$(conexion_replica "$PRIMARIO")'
         PUBLICATION pub_promovida_r$REGION WITH (copy_data = true)" >/dev/null 2>&1 \
     || fallar "no se pudo crear la suscripción $SUB_NUEVA (¿existe pub_promovida_r$REGION en '$PRIMARIO'?)"
registro "'$NODO' suscrito a '$PRIMARIO' ($SUB_NUEVA); copiando la región $REGION..."

# ---------------------------------------------------------------------
# 5. Esperar la copia inicial y comparar.
# ---------------------------------------------------------------------
for i in $(seq 1 60); do
    PEND=$(sql_en "$NODO" "SELECT count(*) FROM pg_subscription_rel r JOIN pg_subscription s ON s.oid = r.srsubid
                           WHERE s.subname = '$SUB_NUEVA' AND r.srsubstate <> 'r'")
    [ "$PEND" = "0" ] && break
    sleep 1
done
[ "$PEND" = "0" ] || fallar "la copia inicial no terminó en 60 s."

CONTEO="SELECT string_agg(n::text, ',') FROM (
          SELECT count(*) AS n FROM app.usuario_r$REGION UNION ALL
          SELECT count(*) FROM app.planta_r$REGION  UNION ALL
          SELECT count(*) FROM app.sensor_r$REGION  UNION ALL
          SELECT count(*) FROM app.cuidado_r$REGION UNION ALL
          SELECT count(*) FROM app.alerta_r$REGION) c"
for i in $(seq 1 30); do
    EN_PRIMARIO=$(sql_en "$PRIMARIO" "$CONTEO")
    EN_NODO=$(sql_en "$NODO" "$CONTEO")
    [ "$EN_PRIMARIO" = "$EN_NODO" ] && break
    sleep 1
done
[ "$EN_PRIMARIO" = "$EN_NODO" ] || fallar "conteos distintos: '$PRIMARIO'=$EN_PRIMARIO, '$NODO'=$EN_NODO"
registro "Sincronizado: usuario,planta,sensor,cuidado,alerta de la región $REGION = $EN_NODO en ambos nodos."

# Sus otras suscripciones (su copia del anillo y las globales) siguieron solas al arrancar.
INACTIVAS=$(sql_en "$NODO" "SELECT coalesce(string_agg(s.subname, ', '), '') FROM pg_subscription s
                            LEFT JOIN pg_stat_subscription st ON st.subid = s.oid AND st.relid IS NULL
                            WHERE s.subenabled AND st.pid IS NULL")
[ -z "$INACTIVAS" ] || registro "AVISO: suscripciones sin proceso en '$NODO': $INACTIVAS"

registro "=== Listo: '$NODO' es copia de la región $REGION; el primario sigue siendo '$PRIMARIO'. ==="
registro "Volver a ser primario es un cambio planeado (D-01 §3)."
