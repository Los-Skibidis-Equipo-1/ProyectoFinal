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
