"""Pruebas de la clase Especie."""

import pytest

from plantas.dominio.especie import Especie
from plantas.dominio.excepciones import (
    CampoVacio,
    ErrorDeValidacion,
    OpcionNoPermitida,
    TipoDeDatoInvalido,
    ValorFueraDeRango,
)


def datos(**cambios):
    base = {
        "nombre_comun": "Monstera",
        "nombre_cientifico": "Monstera deliciosa",
        "humedad_ideal_min": 40,
        "humedad_ideal_max": 70,
        "frecuencia_riego_dias": 7,
        "luz": "indirecta",
        "temp_min": 15,
        "temp_max": 30,
        "fuente": "Real Jardín Botánico",
    }
    base.update(cambios)
    return base


@pytest.fixture
def especie():
    return Especie(**datos())


def test_se_crea_con_datos_validos(especie):
    assert especie.nombre_comun == "Monstera"
    assert especie.nombre_cientifico == "Monstera deliciosa"
    assert (especie.humedad_ideal_min, especie.humedad_ideal_max) == (40, 70)
    assert (especie.temp_min, especie.temp_max) == (15, 30)
    assert especie.frecuencia_riego_dias == 7
    assert especie.luz == "indirecta"
    assert especie.fuente == "Real Jardín Botánico"


def test_los_opcionales_empiezan_vacios(especie):
    assert especie.especie_id is None
    assert especie.cuidados is None


def test_acepta_id_y_cuidados():
    otra = Especie(**datos(especie_id=5, cuidados="  Luz filtrada  "))
    assert otra.especie_id == 5
    assert otra.cuidados == "Luz filtrada"


@pytest.mark.parametrize("valor", [0, -1, "abc"])
def test_id_invalido(valor):
    with pytest.raises(ErrorDeValidacion):
        Especie(**datos(especie_id=valor))


def test_los_textos_se_limpian_y_se_validan():
    otra = Especie(**datos(nombre_comun="  Monstera  ", luz=" DIRECTA "))
    assert otra.nombre_comun == "Monstera"
    assert otra.luz == "directa"


@pytest.mark.parametrize(
    "campo", ["nombre_comun", "nombre_cientifico", "fuente"]
)
def test_los_textos_obligatorios_no_pueden_estar_vacios(campo):
    with pytest.raises(CampoVacio):
        Especie(**datos(**{campo: "   "}))


def test_nombre_comun_largo():
    with pytest.raises(ValorFueraDeRango, match="80"):
        Especie(**datos(nombre_comun="x" * 81))


def test_nombre_cientifico_largo():
    with pytest.raises(ValorFueraDeRango, match="120"):
        Especie(**datos(nombre_cientifico="x" * 121))


def test_luz_fuera_del_catalogo():
    with pytest.raises(OpcionNoPermitida):
        Especie(**datos(luz="neón"))


@pytest.mark.parametrize("valor", [0, 366, 2.5, "mucho"])
def test_frecuencia_de_riego_invalida(valor):
    with pytest.raises(ErrorDeValidacion):
        Especie(**datos(frecuencia_riego_dias=valor))


@pytest.mark.parametrize(
    ("minimo", "maximo"), [(70, 40), (50, 50), (-1, 50), (10, 101)]
)
def test_rango_de_humedad_invalido(minimo, maximo):
    with pytest.raises(ValorFueraDeRango):
        Especie(**datos(humedad_ideal_min=minimo, humedad_ideal_max=maximo))


@pytest.mark.parametrize(
    ("minimo", "maximo"), [(30, 10), (20, 20), (-21, 10), (10, 61)]
)
def test_rango_de_temperatura_invalido(minimo, maximo):
    with pytest.raises(ValorFueraDeRango):
        Especie(**datos(temp_min=minimo, temp_max=maximo))


def test_los_rangos_extremos_son_validos():
    otra = Especie(
        **datos(
            humedad_ideal_min=0,
            humedad_ideal_max=100,
            temp_min=-20,
            temp_max=60,
        )
    )
    assert otra.humedad_ideal_max == 100
    assert otra.temp_min == -20


def test_cambiar_rango_de_humedad(especie):
    especie.cambiar_rango_humedad(30, 60)
    assert (especie.humedad_ideal_min, especie.humedad_ideal_max) == (30, 60)


def test_un_cambio_invalido_no_modifica_el_rango(especie):
    with pytest.raises(ValorFueraDeRango):
        especie.cambiar_rango_humedad(90, 20)
    assert (especie.humedad_ideal_min, especie.humedad_ideal_max) == (40, 70)
    with pytest.raises(ValorFueraDeRango):
        especie.cambiar_rango_temperatura(50, 10)
    assert (especie.temp_min, especie.temp_max) == (15, 30)


def test_los_rangos_no_se_asignan_de_uno_en_uno(especie):
    with pytest.raises(AttributeError):
        especie.humedad_ideal_min = 10
    with pytest.raises(AttributeError):
        especie.temp_max = 99


def test_el_nombre_cientifico_no_cambia(especie):
    with pytest.raises(AttributeError):
        especie.nombre_cientifico = "Otra"


def test_los_setters_validan(especie):
    especie.nombre_comun = " Costilla de Adán "
    especie.frecuencia_riego_dias = "10"
    especie.luz = "sombra"
    especie.fuente = "Otra fuente"
    especie.cuidados = "   "
    assert especie.nombre_comun == "Costilla de Adán"
    assert especie.frecuencia_riego_dias == 10
    assert especie.luz == "sombra"
    assert especie.fuente == "Otra fuente"
    assert especie.cuidados is None
    with pytest.raises(OpcionNoPermitida):
        especie.luz = "neón"
    assert especie.luz == "sombra"


def test_humedad_en_rango(especie):
    assert especie.humedad_en_rango(40)
    assert especie.humedad_en_rango(55)
    assert especie.humedad_en_rango(70)
    assert not especie.humedad_en_rango(39.9)
    assert not especie.humedad_en_rango(70.1)


def test_humedad_en_rango_valida_el_dato(especie):
    with pytest.raises(ValorFueraDeRango):
        especie.humedad_en_rango(150)
    with pytest.raises(TipoDeDatoInvalido):
        especie.humedad_en_rango("alta")


def test_igualdad_por_nombre_cientifico(especie):
    igual = Especie(
        **datos(nombre_comun="Otra", nombre_cientifico="MONSTERA DELICIOSA")
    )
    distinta = Especie(**datos(nombre_cientifico="Ficus lyrata"))
    assert especie == igual
    assert hash(especie) == hash(igual)
    assert especie != distinta
    assert especie != "Monstera deliciosa"
    assert len({especie, igual, distinta}) == 2


def test_repr(especie):
    assert repr(especie) == "Especie('Monstera deliciosa')"
