"""Pruebas de la jerarquía de excepciones."""

from uuid import UUID

import pytest

from plantas.dominio.excepciones import (
    CampoVacio,
    ConfiguracionInvalida,
    CorreoYaRegistrado,
    CredencialesInvalidas,
    DirectorioNoDisponible,
    ErrorDeAutenticacion,
    ErrorDeInfraestructura,
    ErrorDeNegocio,
    ErrorDeValidacion,
    ErrorPlantas,
    FechaInvalida,
    LecturaFueraDeRango,
    LecturaNoGuardada,
    NodoNoDisponible,
    OpcionNoPermitida,
    PlantaInactiva,
    PlantaNoEncontrada,
    TipoDeDatoInvalido,
    TokenExpirado,
    TokenInvalido,
    ValorFueraDeRango,
)

PLANTA = UUID("11111111-1111-1111-1111-111111111111")
SENSOR = UUID("22222222-2222-2222-2222-222222222222")

VALIDACION = [
    CampoVacio,
    TipoDeDatoInvalido,
    ValorFueraDeRango,
    OpcionNoPermitida,
    FechaInvalida,
    LecturaFueraDeRango,
]


@pytest.mark.parametrize("clase", VALIDACION)
def test_los_errores_de_validacion_heredan_de_la_base(clase):
    assert issubclass(clase, ErrorDeValidacion)
    assert issubclass(clase, ErrorPlantas)
    assert issubclass(clase, Exception)


@pytest.mark.parametrize(
    "clase", [PlantaNoEncontrada, PlantaInactiva, CorreoYaRegistrado]
)
def test_los_errores_de_negocio_heredan_de_la_base(clase):
    assert issubclass(clase, ErrorDeNegocio)
    assert issubclass(clase, ErrorPlantas)


@pytest.mark.parametrize(
    "clase",
    [
        NodoNoDisponible,
        DirectorioNoDisponible,
        LecturaNoGuardada,
        ConfiguracionInvalida,
    ],
)
def test_los_errores_de_infraestructura_heredan_de_la_base(clase):
    assert issubclass(clase, ErrorDeInfraestructura)
    assert issubclass(clase, ErrorPlantas)


def test_las_tres_ramas_son_distintas():
    ramas = [ErrorDeValidacion, ErrorDeNegocio, ErrorDeInfraestructura]
    for rama in ramas:
        for otra in ramas:
            if rama is not otra:
                assert not issubclass(rama, otra)


def test_atrapar_la_base_atrapa_cualquier_error_propio():
    errores = [
        CampoVacio("vacío"),
        ValorFueraDeRango("fuera"),
        PlantaNoEncontrada(PLANTA, 2),
        PlantaInactiva(PLANTA, "fallecida"),
        CorreoYaRegistrado(),
        NodoNoDisponible(1, "MongoDB"),
        DirectorioNoDisponible(),
        LecturaNoGuardada(SENSOR, 3),
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
    error = PlantaNoEncontrada(PLANTA, 2)
    assert error.planta_id == PLANTA
    assert error.region_id == 2
    assert str(error) == f"La planta {PLANTA} no existe en la región 2"


def test_planta_inactiva_dice_planta_y_estatus():
    error = PlantaInactiva(PLANTA, "fallecida")
    assert error.planta_id == PLANTA
    assert error.estatus == "fallecida"
    assert str(error) == (
        f"La planta {PLANTA} no está activa (estatus: fallecida)"
    )


def test_sqlstate_coincide_con_los_errores_de_a5():
    # P0002 (no_data_found) y 23514 (check_violation), de db/04_funciones.sql
    assert PlantaNoEncontrada.sqlstate == "P0002"
    assert PlantaInactiva.sqlstate == "23514"
    assert ErrorDeValidacion.sqlstate == "23514"
    assert CampoVacio.sqlstate == "23514"
    assert CorreoYaRegistrado.sqlstate == "23505"
    assert ErrorPlantas.sqlstate is None


def test_correo_ya_registrado_no_incluye_el_correo():
    error = CorreoYaRegistrado()
    assert str(error) == "Ese correo ya está registrado"
    assert not hasattr(error, "correo")


def test_nodo_no_disponible_dice_region_y_servicio():
    error = NodoNoDisponible(3, "MongoDB")
    assert error.region_id == 3
    assert error.servicio == "MongoDB"
    assert "MongoDB" in str(error)
    assert "región 3" in str(error)


def test_directorio_no_disponible_pide_intentar_de_nuevo():
    assert "intenta de nuevo" in str(DirectorioNoDisponible())


def test_lectura_no_guardada_dice_sensor_e_intentos():
    error = LecturaNoGuardada(SENSOR, 3)
    assert error.sensor_id == SENSOR
    assert error.intentos == 3
    assert "3 intentos" in str(error)


def test_los_errores_de_infraestructura_no_tienen_sqlstate():
    assert ErrorDeInfraestructura.sqlstate is None
    assert NodoNoDisponible.sqlstate is None


def test_una_lectura_fuera_de_rango_tambien_es_un_valor_fuera_de_rango():
    assert issubclass(LecturaFueraDeRango, ValorFueraDeRango)
    with pytest.raises(ValorFueraDeRango):
        raise LecturaFueraDeRango("lectura mala", "humedad", 180)


AUTENTICACION = [CredencialesInvalidas, TokenInvalido, TokenExpirado]


@pytest.mark.parametrize("clase", AUTENTICACION)
def test_los_errores_de_autenticacion_son_de_negocio(clase):
    assert issubclass(clase, ErrorDeAutenticacion)
    assert issubclass(clase, ErrorDeNegocio)
    assert issubclass(clase, ErrorPlantas)
    assert not issubclass(clase, ErrorDeValidacion)
    assert not issubclass(clase, ErrorDeInfraestructura)


def test_un_token_expirado_tambien_es_un_token_invalido():
    assert issubclass(TokenExpirado, TokenInvalido)
    assert not issubclass(TokenInvalido, TokenExpirado)


def test_los_mensajes_de_autenticacion_son_genericos():
    assert str(CredencialesInvalidas()) == "Correo o contraseña incorrectos"
    assert str(TokenInvalido()) == "El token no es válido"
    assert str(TokenExpirado()) == "El token ya venció"


def test_la_configuracion_invalida_dice_la_variable():
    error = ConfiguracionInvalida("JWT_SECRET", "falta la llave")
    assert error.variable == "JWT_SECRET"
    assert "JWT_SECRET" in str(error)
