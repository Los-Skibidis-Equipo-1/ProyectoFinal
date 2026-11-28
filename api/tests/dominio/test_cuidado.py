"""Pruebas de la clase Cuidado."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from plantas.dominio.cuidado import Cuidado
from plantas.dominio.excepciones import (
    ErrorDeValidacion,
    FechaInvalida,
    OpcionNoPermitida,
    TipoDeDatoInvalido,
    ValorFueraDeRango,
)

PLANTA = "33333333-3333-3333-3333-333333333333"
CUIDADO = "44444444-4444-4444-4444-444444444444"
AHORA = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)


def datos(**cambios):
    base = {
        "region_id": 1,
        "planta_id": PLANTA,
        "tipo": "poda",
        "fecha_hora": AHORA - timedelta(hours=2),
        "ahora": AHORA,
    }
    base.update(cambios)
    return base


def test_se_crea_con_datos_validos():
    cuidado = Cuidado(**datos(cuidado_id=CUIDADO, notas="  Hojas secas  "))
    assert cuidado.region_id == 1
    assert cuidado.planta_id == UUID(PLANTA)
    assert cuidado.cuidado_id == UUID(CUIDADO)
    assert cuidado.tipo == "poda"
    assert cuidado.fecha_hora == AHORA - timedelta(hours=2)
    assert cuidado.cantidad_ml is None
    assert cuidado.notas == "Hojas secas"
    assert not cuidado.es_riego


def test_genera_un_uuid_si_no_se_da_id():
    assert Cuidado(**datos()).cuidado_id != Cuidado(**datos()).cuidado_id


def test_sin_fecha_usa_el_momento_actual():
    cuidado = Cuidado(region_id=1, planta_id=PLANTA, tipo="otro")
    assert datetime.now(UTC) - cuidado.fecha_hora < timedelta(seconds=5)


def test_un_riego_con_cantidad():
    riego = Cuidado(**datos(tipo="riego", cantidad_ml="250"))
    assert riego.es_riego
    assert riego.cantidad_ml == 250


def test_un_riego_sin_cantidad_es_valido():
    assert Cuidado(**datos(tipo="riego")).cantidad_ml is None


@pytest.mark.parametrize("valor", [0, -5, 20001])
def test_cantidad_de_riego_fuera_de_rango(valor):
    with pytest.raises(ValorFueraDeRango):
        Cuidado(**datos(tipo="riego", cantidad_ml=valor))


def test_cantidad_de_riego_debe_ser_entera():
    with pytest.raises(TipoDeDatoInvalido):
        Cuidado(**datos(tipo="riego", cantidad_ml=250.5))


@pytest.mark.parametrize("tipo", ["fertilizado", "poda", "trasplante", "otro"])
def test_solo_un_riego_lleva_cantidad(tipo):
    with pytest.raises(ErrorDeValidacion, match="Solo un riego"):
        Cuidado(**datos(tipo=tipo, cantidad_ml=100))


def test_el_tipo_se_normaliza_y_se_valida():
    assert Cuidado(**datos(tipo=" RIEGO ")).tipo == "riego"
    with pytest.raises(OpcionNoPermitida):
        Cuidado(**datos(tipo="baile"))


def test_fecha_futura_o_sin_zona_horaria():
    with pytest.raises(FechaInvalida, match="futuro"):
        Cuidado(**datos(fecha_hora=AHORA + timedelta(minutes=1)))
    with pytest.raises(FechaInvalida, match="zona horaria"):
        Cuidado(**datos(fecha_hora=datetime(2026, 1, 1)))


def test_notas_opcionales_y_con_largo_maximo():
    assert Cuidado(**datos(notas="   ")).notas is None
    with pytest.raises(ValorFueraDeRango, match="500"):
        Cuidado(**datos(notas="x" * 501))


def test_ids_invalidos():
    with pytest.raises(TipoDeDatoInvalido):
        Cuidado(**datos(planta_id="123"))
    with pytest.raises(ValorFueraDeRango):
        Cuidado(**datos(region_id=7))


def test_atajo_para_un_riego():
    riego = Cuidado.riego(
        region_id=2,
        planta_id=PLANTA,
        cantidad_ml=300,
        notas="Con agua reposada",
        fecha_hora=AHORA - timedelta(hours=1),
        ahora=AHORA,
    )
    assert riego.tipo == "riego"
    assert riego.es_riego
    assert riego.cantidad_ml == 300
    assert riego.region_id == 2
    assert riego.notas == "Con agua reposada"


def test_un_cuidado_no_se_modifica():
    cuidado = Cuidado(**datos())
    for campo in (
        "region_id",
        "cuidado_id",
        "planta_id",
        "tipo",
        "fecha_hora",
        "cantidad_ml",
        "notas",
    ):
        with pytest.raises(AttributeError):
            setattr(cuidado, campo, None)


def test_igualdad_por_region_e_id():
    uno = Cuidado(**datos(cuidado_id=CUIDADO))
    otro = Cuidado(**datos(cuidado_id=CUIDADO, tipo="otro"))
    otra_region = Cuidado(**datos(cuidado_id=CUIDADO, region_id=2))
    assert uno == otro
    assert hash(uno) == hash(otro)
    assert uno != otra_region
    assert uno != "cuidado"
    assert len({uno, otro, otra_region}) == 2


def test_repr():
    cuidado = Cuidado(**datos(cuidado_id=CUIDADO))
    assert repr(cuidado) == (
        f"Cuidado(cuidado_id={CUIDADO}, tipo='poda', planta_id={PLANTA})"
    )
