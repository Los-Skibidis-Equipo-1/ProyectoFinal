"""Comprueba que los catálogos coinciden con los CHECK del esquema SQL."""

import re
from pathlib import Path

import pytest

from plantas.dominio import catalogos

ESQUEMA = Path(__file__).resolve().parents[2] / "db" / "01_esquema.sql"

# (nombre del CHECK en el esquema, catálogo de Python)
CATALOGOS = [
    ("ck_planta_espacio", catalogos.TIPOS_ESPACIO),
    ("ck_planta_estatus", catalogos.ESTATUS_PLANTA),
    ("ck_cuidado_tipo", catalogos.TIPOS_CUIDADO),
    ("ck_usuario_rol", catalogos.ROLES),
    ("ck_especie_luz", catalogos.NIVELES_LUZ),
    ("ck_sensor_tipo", catalogos.TIPOS_SENSOR),
    ("ck_alerta_tipo", catalogos.TIPOS_ALERTA),
    ("ck_alerta_estado", catalogos.ESTADOS_ALERTA),
]


def opciones_del_esquema(nombre_check: str) -> tuple[str, ...]:
    sql = ESQUEMA.read_text(encoding="utf-8")
    patron = rf"{nombre_check}\s+CHECK\s*\(\s*\w+\s+IN\s*\(([^)]*)\)"
    encontrado = re.search(patron, sql)
    assert encontrado, f"No se encontró {nombre_check} en db/01_esquema.sql"
    return tuple(re.findall(r"'([^']+)'", encontrado.group(1)))


def test_el_esquema_sql_existe():
    assert ESQUEMA.is_file()


@pytest.mark.parametrize(("nombre_check", "catalogo"), CATALOGOS)
def test_el_catalogo_coincide_con_el_esquema(nombre_check, catalogo):
    assert opciones_del_esquema(nombre_check) == catalogo


def limites_del_esquema(patron: str) -> tuple[int, int]:
    sql = ESQUEMA.read_text(encoding="utf-8")
    encontrado = re.search(patron, sql)
    assert encontrado, f"No se encontró {patron!r} en db/01_esquema.sql"
    return int(encontrado.group(1)), int(encontrado.group(2))


def test_los_limites_numericos_coinciden_con_el_esquema():
    assert limites_del_esquema(
        r"ck_region_id\s+CHECK\s*\(region_id BETWEEN (-?\d+) AND (-?\d+)"
    ) == (catalogos.REGION_MIN, catalogos.REGION_MAX)
    assert limites_del_esquema(
        r"ck_planta_humedad.*?humedad_actual BETWEEN (-?\d+) AND (-?\d+)"
    ) == (catalogos.HUMEDAD_MIN, catalogos.HUMEDAD_MAX)
    assert limites_del_esquema(
        r"ck_especie_riego\s+CHECK\s*\(frecuencia_riego_dias "
        r"BETWEEN (-?\d+) AND (-?\d+)"
    ) == (catalogos.RIEGO_DIAS_MIN, catalogos.RIEGO_DIAS_MAX)
    assert limites_del_esquema(
        r"ck_especie_temp_rango\s+CHECK\s*\(temp_min >= (-?\d+) "
        r"AND temp_max <= (-?\d+)"
    ) == (catalogos.TEMPERATURA_MIN, catalogos.TEMPERATURA_MAX)
