"""Opciones permitidas para los campos de catálogo.

Deben coincidir con los CHECK de db/01_esquema.sql; la prueba
tests/test_catalogos.py lo comprueba para que no se desincronicen.
"""

TIPOS_ESPACIO = ("casa", "departamento", "oficina", "patio")
ESTATUS_PLANTA = ("activa", "fallecida", "regalada")
TIPOS_CUIDADO = ("riego", "fertilizado", "poda", "trasplante", "otro")
ROLES = ("usuario", "admin")
NIVELES_LUZ = ("sombra", "indirecta", "directa")
TIPOS_SENSOR = ("humedad", "ambiente")
TIPOS_ALERTA = (
    "humedad_baja",
    "humedad_alta",
    "riego_pendiente",
    "temperatura",
)
ESTADOS_ALERTA = ("pendiente", "atendida")

# Límites numéricos del esquema.
REGION_MIN, REGION_MAX = 1, 3
HUMEDAD_MIN, HUMEDAD_MAX = 0, 100
TEMPERATURA_MIN, TEMPERATURA_MAX = -20, 60
RIEGO_DIAS_MIN, RIEGO_DIAS_MAX = 1, 365
