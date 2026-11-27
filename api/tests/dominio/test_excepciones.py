"""Pruebas de la jerarquía de excepciones."""

import pytest

from plantas.dominio.excepciones import (
    CampoVacio,
    ErrorDeNegocio,
    ErrorDeValidacion,
    ErrorPlantas,
    FechaInvalida,
    OpcionNoPermitida,
    PlantaInactiva,
    PlantaNoEncontrada,
    TipoDeDatoInvalido,
    ValorFueraDeRango,
)

VALIDACION = [
    CampoVacio,
    TipoDeDatoInvalido,
    ValorFueraDeRango,
    OpcionNoPermitida,
    FechaInvalida,
]


@pytest.mark.parametrize("clase", VALIDACION)
def test_los_errores_de_validacion_heredan_de_la_base(clase):
    assert issubclass(clase, ErrorDeValidacion)
    assert issubclass(clase, ErrorPlantas)
    assert issubclass(clase, Exception)


@pytest.mark.parametrize("clase", [PlantaNoEncontrada, PlantaInactiva])
def test_los_errores_de_negocio_heredan_de_la_base(clase):
    assert issubclass(clase, ErrorDeNegocio)
    assert issubclass(clase, ErrorPlantas)


def test_validacion_y_negocio_son_ramas_distintas():
    assert not issubclass(ErrorDeValidacion, ErrorDeNegocio)
    assert not issubclass(ErrorDeNegocio, ErrorDeValidacion)


def test_atrapar_la_base_atrapa_cualquier_error_propio():
    errores = [
        CampoVacio("vacío"),
        ValorFueraDeRango("fuera"),
        PlantaNoEncontrada(7, 2),
        PlantaInactiva(7, "fallecida"),
    ]
    for error in errores:
        with pytest.raises(ErrorPlantas):
            raise error


def test_un_error_ajeno_no_es_de_la_aplicacion():
    assert not issubclass(ValueError, ErrorPlantas)


def test_el_error_de_validacion_guarda_mensaje_campo_y_valor():
    error = ValorFueraDeRango("humedad fuera de rango", "humedad", 150)
    assert str(error) == "humedad fuera de rango"
    assert error.mensaje == "humedad fuera de rango"
    assert error.campo == "humedad"
    assert error.valor == 150


def test_el_campo_y_el_valor_son_opcionales():
    error = ErrorDeValidacion("dato inválido")
    assert error.campo is None
    assert error.valor is None


def test_planta_no_encontrada_dice_planta_y_region():
    error = PlantaNoEncontrada(7, 2)
    assert error.planta_id == 7
    assert error.region_id == 2
    assert str(error) == "La planta 7 no existe en la región 2"


def test_planta_inactiva_dice_planta_y_estatus():
    error = PlantaInactiva(7, "fallecida")
    assert error.planta_id == 7
    assert error.estatus == "fallecida"
    assert str(error) == "La planta 7 no está activa (estatus: fallecida)"


def test_sqlstate_coincide_con_los_errores_de_a5():
    # P0002 (no_data_found) y 23514 (check_violation), de db/04_funciones.sql
    assert PlantaNoEncontrada.sqlstate == "P0002"
    assert PlantaInactiva.sqlstate == "23514"
    assert ErrorDeValidacion.sqlstate == "23514"
    assert CampoVacio.sqlstate == "23514"
    assert ErrorPlantas.sqlstate is None
