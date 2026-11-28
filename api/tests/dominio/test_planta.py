"""Pruebas de la clase Planta."""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import pytest

from plantas.dominio.excepciones import (
    CampoVacio,
    ErrorDeValidacion,
    FechaInvalida,
    OpcionNoPermitida,
    PlantaInactiva,
    TipoDeDatoInvalido,
    ValorFueraDeRango,
)
from plantas.dominio.planta import Planta

USUARIO = "22222222-2222-2222-2222-222222222222"
PLANTA = "33333333-3333-3333-3333-333333333333"
AHORA = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)
HOY = date(2026, 11, 27)


def datos(**cambios):
    base = {
        "region_id": 1,
        "usuario_id": USUARIO,
        "especie_id": 4,
        "apodo": "Monstera de la sala",
        "tipo_espacio": "casa",
        "ahora": AHORA,
        "hoy": HOY,
    }
    base.update(cambios)
    return base


@pytest.fixture
def planta():
    return Planta(**datos(planta_id=PLANTA))


def test_se_crea_con_datos_validos(planta):
    assert planta.region_id == 1
    assert planta.usuario_id == UUID(USUARIO)
    assert planta.especie_id == 4
    assert planta.apodo == "Monstera de la sala"
    assert planta.tipo_espacio == "casa"
    assert planta.planta_id == UUID(PLANTA)


def test_los_opcionales_empiezan_vacios(planta):
    assert planta.ubicacion_descripcion is None
    assert planta.fecha_adquisicion is None
    assert planta.humedad_actual is None
    assert planta.fecha_ultima_lectura is None
    assert planta.estatus == "activa"
    assert planta.esta_activa


def test_genera_un_uuid_si_no_se_da_id():
    assert Planta(**datos()).planta_id != Planta(**datos()).planta_id


def test_un_id_invalido():
    with pytest.raises(TipoDeDatoInvalido):
        Planta(**datos(usuario_id="123"))
    with pytest.raises(ErrorDeValidacion):
        Planta(**datos(especie_id=0))


def test_apodo_obligatorio_y_con_largo_maximo():
    with pytest.raises(CampoVacio):
        Planta(**datos(apodo="  "))
    with pytest.raises(ValorFueraDeRango, match="60"):
        Planta(**datos(apodo="x" * 61))


def test_tipo_de_espacio_valido_e_invalido():
    assert Planta(**datos(tipo_espacio=" Patio ")).tipo_espacio == "patio"
    with pytest.raises(OpcionNoPermitida):
        Planta(**datos(tipo_espacio="azotea"))


def test_ubicacion_opcional():
    assert (
        Planta(**datos(ubicacion_descripcion="  ")).ubicacion_descripcion
        is None
    )
    otra = Planta(**datos(ubicacion_descripcion=" Junto a la ventana "))
    assert otra.ubicacion_descripcion == "Junto a la ventana"
    with pytest.raises(ValorFueraDeRango, match="100"):
        Planta(**datos(ubicacion_descripcion="x" * 101))


def test_fecha_de_adquisicion():
    assert Planta(**datos(fecha_adquisicion=HOY)).fecha_adquisicion == HOY
    with pytest.raises(FechaInvalida):
        Planta(**datos(fecha_adquisicion=HOY + timedelta(days=1)))


def test_estatus_inicial_invalido():
    with pytest.raises(OpcionNoPermitida):
        Planta(**datos(estatus="perdida"))


def test_se_crea_con_una_lectura_completa():
    lectura = AHORA - timedelta(minutes=5)
    planta = Planta(
        **datos(humedad_actual="55,5", fecha_ultima_lectura=lectura)
    )
    assert planta.humedad_actual == 55.5
    assert planta.fecha_ultima_lectura == lectura


def test_humedad_y_fecha_van_juntas_o_ninguna():
    with pytest.raises(ErrorDeValidacion, match="juntas"):
        Planta(**datos(humedad_actual=50))
    with pytest.raises(ErrorDeValidacion, match="juntas"):
        Planta(**datos(fecha_ultima_lectura=AHORA))


def test_lectura_inicial_invalida():
    with pytest.raises(ValorFueraDeRango):
        Planta(**datos(humedad_actual=150, fecha_ultima_lectura=AHORA))
    with pytest.raises(FechaInvalida):
        Planta(
            **datos(
                humedad_actual=50,
                fecha_ultima_lectura=AHORA + timedelta(hours=1),
            )
        )


def test_registrar_lectura_actualiza_las_dos_cosas(planta):
    momento = AHORA - timedelta(minutes=1)
    planta.registrar_lectura_humedad(62, momento, AHORA)
    assert planta.humedad_actual == 62.0
    assert planta.fecha_ultima_lectura == momento


def test_una_lectura_invalida_no_cambia_nada(planta):
    anterior = AHORA - timedelta(minutes=10)
    planta.registrar_lectura_humedad(40, anterior, AHORA)
    with pytest.raises(ValorFueraDeRango):
        planta.registrar_lectura_humedad(150, AHORA, AHORA)
    with pytest.raises(FechaInvalida):
        planta.registrar_lectura_humedad(50, AHORA + timedelta(hours=1), AHORA)
    assert planta.humedad_actual == 40.0
    assert planta.fecha_ultima_lectura == anterior


def test_sin_sensor_por_defecto_y_se_puede_marcar(planta):
    assert planta.tiene_sensor_humedad is False
    planta.marcar_sensor_humedad(True)
    assert planta.tiene_sensor_humedad is True
    planta.marcar_sensor_humedad(False)
    assert planta.tiene_sensor_humedad is False


def test_el_sensor_debe_ser_booleano(planta):
    with pytest.raises(TipoDeDatoInvalido):
        planta.marcar_sensor_humedad(1)
    with pytest.raises(TipoDeDatoInvalido):
        Planta(**datos(tiene_sensor_humedad="si"))
    assert Planta(**datos(tiene_sensor_humedad=True)).tiene_sensor_humedad


def test_una_planta_sin_sensor_funciona_con_normalidad(planta):
    planta.verificar_activa()
    planta.apodo = "Nuevo apodo"
    assert planta.humedad_actual is None
    assert not planta.tiene_sensor_humedad


def test_cambiar_estatus(planta):
    planta.cambiar_estatus("Fallecida")
    assert planta.estatus == "fallecida"
    assert not planta.esta_activa
    with pytest.raises(OpcionNoPermitida):
        planta.cambiar_estatus("perdida")
    assert planta.estatus == "fallecida"


def test_verificar_activa_lanza_planta_inactiva(planta):
    planta.verificar_activa()
    planta.cambiar_estatus("regalada")
    with pytest.raises(PlantaInactiva) as info:
        planta.verificar_activa()
    assert info.value.planta_id == UUID(PLANTA)
    assert info.value.estatus == "regalada"


def test_los_setters_validan(planta):
    planta.apodo = "  Otra  "
    planta.tipo_espacio = "oficina"
    planta.ubicacion_descripcion = "Escritorio"
    assert (planta.apodo, planta.tipo_espacio) == ("Otra", "oficina")
    assert planta.ubicacion_descripcion == "Escritorio"
    with pytest.raises(OpcionNoPermitida):
        planta.tipo_espacio = "azotea"
    assert planta.tipo_espacio == "oficina"


def test_los_identificadores_no_cambian(planta):
    for campo in ("planta_id", "usuario_id", "region_id", "especie_id"):
        with pytest.raises(AttributeError):
            setattr(planta, campo, 1)
    with pytest.raises(AttributeError):
        planta.humedad_actual = 10
    with pytest.raises(AttributeError):
        planta.estatus = "fallecida"


def test_igualdad_por_region_e_id(planta):
    misma = Planta(**datos(planta_id=PLANTA, apodo="Otro"))
    otra_region = Planta(**datos(planta_id=PLANTA, region_id=2))
    assert planta == misma
    assert hash(planta) == hash(misma)
    assert planta != otra_region
    assert planta != "planta"
    assert len({planta, misma, otra_region}) == 2


def test_repr(planta):
    assert repr(planta) == (
        f"Planta(planta_id={PLANTA}, region_id=1, estatus='activa')"
    )
