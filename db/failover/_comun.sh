#!/usr/bin/env bash
# =====================================================================
# Funciones comunes de promover.sh y reincorporar.sh (A12, D-01 §3 y §8)
# Responsable: Alexa Yalee Sánchez Tejeda · IA: generado y revisado (Claude)
#
# Variables de entorno:
#   NODO_NORTE_HOST, NODO_CENTRO_HOST, NODO_SUR_HOST   dirección de cada nodo
#   NODO_NORTE_PORT, NODO_CENTRO_PORT, NODO_SUR_PORT   (opcional, 5432)
#   PGPASSWORD          contraseña de postgres en los nodos
#   PG_PASS_REPLICA     contraseña de plantas_replica (para crear suscripciones)
#   ESCRITOR_GLOBALES   nodo que escribe las tablas globales (norte por defecto)
# =====================================================================
set -euo pipefail
export PGOPTIONS="${PGOPTIONS:--c client_min_messages=warning}"   # sin avisos NOTICE en la salida

: "${NODO_NORTE_HOST:?Falta NODO_NORTE_HOST}"
: "${NODO_CENTRO_HOST:?Falta NODO_CENTRO_HOST}"
: "${NODO_SUR_HOST:?Falta NODO_SUR_HOST}"
ESCRITOR_GLOBALES="${ESCRITOR_GLOBALES:-norte}"

registro() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
fallar()   { registro "ERROR: $*" >&2; exit 1; }

validar_nodo() {
    case "$1" in norte|centro|sur) ;; *) fallar "nodo inválido '$1' (usa norte, centro o sur)";; esac
}

host_de() {
    case "$1" in norte) echo "$NODO_NORTE_HOST";; centro) echo "$NODO_CENTRO_HOST";; sur) echo "$NODO_SUR_HOST";; esac
}
port_de() {
    case "$1" in
        norte)  echo "${NODO_NORTE_PORT:-5432}";;
        centro) echo "${NODO_CENTRO_PORT:-5432}";;
        sur)    echo "${NODO_SUR_PORT:-5432}";;
    esac
}

# ¿El nodo acepta conexiones? (3 s de espera)
vivo() {
    pg_isready -q -h "$(host_de "$1")" -p "$(port_de "$1")" -t 3 >/dev/null 2>&1
}

# Ejecuta SQL en un nodo como postgres y devuelve el resultado sin formato.
sql_en() {
    local nodo="$1"; shift
    psql "host=$(host_de "$nodo") port=$(port_de "$nodo") dbname=plantas user=postgres connect_timeout=5" \
         -X -q -tA -v ON_ERROR_STOP=1 -c "$*"
}

# Cadena de conexión que usan las suscripciones.
conexion_replica() {
    echo "host=$(host_de "$1") port=$(port_de "$1") dbname=plantas user=plantas_replica password=${PG_PASS_REPLICA:?Falta PG_PASS_REPLICA} sslmode=prefer"
}

# Topología del anillo (la misma de la tabla fragmento, D-01 §3).
region_de()  { case "$1" in norte) echo 1;; centro) echo 2;; sur) echo 3;; esac; }
copia_de()   { case "$1" in norte) echo centro;; centro) echo sur;; sur) echo norte;; esac; }
tercero_de() { case "$1" in norte) echo sur;; centro) echo norte;; sur) echo centro;; esac; }
# Región que el nodo guarda como copia (la de su nodo anterior en el anillo).
region_copiada_por() { case "$1" in norte) echo 3;; centro) echo 1;; sur) echo 2;; esac; }

TABLAS_FRAGMENTO=(usuario planta sensor cuidado alerta)
