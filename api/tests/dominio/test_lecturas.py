"""Pruebas de las lecturas de sensores (clase base y dos tipos)."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from plantas.dominio.excepciones import (
    CampoVacio,
    ErrorDeValidacion,
    FechaInvalida,
    LecturaFueraDeRango,
    OpcionNoPermitida,
    TipoDeDatoInvalido,
    ValorFueraDeRango,
)
from plantas.dominio.lecturas import (
    LecturaAmbiente,
    LecturaHumedad,
    LecturaSensor,
)

SENSOR = "22222222-2222-2222-2222-222222222222"
PLANTA = "33333333-3333-3333-3333-333333333333"
AHORA = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)


def comunes(**cambios):
    base = {
        "sensor_id": SENSOR,
        "planta_id": PLANTA,
        "region_id": 2,
        "timestamp": AHORA - timedelta(minutes=5),
        "ahora": AHORA,
    }
    base.update(cambios)
    return base


def humedad(**cambios):
    return LecturaHumedad(humedad_suelo_pct=45.5, **comunes(**cambios))


def ambiente(**cambios):
    return LecturaAmbiente(
        temperatura_c=22.5, humedad_relativa_pct=60, **comunes(**cambios)
    )


# --- herencia y clase base -------------------------------------------------


def test_los_dos_tipos_heredan_de_la_clase_base():
    assert issubclass(LecturaHumedad, LecturaSensor)
    assert issubclass(LecturaAmbiente, LecturaSensor)


def test_la_clase_base_no_se_puede_crear_directamente():
    with pytest.raises(TypeError):
        LecturaSensor(**comunes())


def test_cada_clase_tiene_su_tipo():
    assert LecturaHumedad.tipo == "humedad"
    assert LecturaAmbiente.tipo == "ambiente"


# --- datos comunes ---------------------------------------------------------


@pytest.mark.parametrize("crear", [humedad, ambiente])
def test_los_datos_comunes_se_guardan(crear):
    lectura = crear()
    assert lectura.sensor_id == UUID(SENSOR)
    assert lectura.planta_id == UUID(PLANTA)
    assert lectura.region_id == 2
    assert lectura.timestamp == AHORA - timedelta(minutes=5)


@pytest.mark.parametrize("crear", [humedad, ambiente])
def test_los_datos_comunes_son_de_solo_lectura(crear):
    lectura = crear()
    for campo in ("sensor_id", "planta_id", "region_id", "timestamp"):
        with pytest.raises(AttributeError):
            setattr(lectura, campo, None)


@pytest.mark.parametrize("crear", [humedad, ambiente])
def test_sin_timestamp_se_usa_la_hora_actual(crear):
    lectura = crear(timestamp=None, ahora=None)
    assert abs(datetime.now(UTC) - lectura.timestamp) < timedelta(seconds=5)


@pytest.mark.parametrize("crear", [humedad, ambiente])
def test_un_timestamp_futuro_se_rechaza(crear):
    with pytest.raises(FechaInvalida):
        crear(timestamp=AHORA + timedelta(minutes=1))


@pytest.mark.parametrize("crear", [humedad, ambiente])
def test_un_timestamp_sin_zona_horaria_se_rechaza(crear):
    with pytest.raises(FechaInvalida):
        crear(timestamp=datetime(2026, 11, 27, 11, 0))


@pytest.mark.parametrize("crear", [humedad, ambiente])
def test_un_sensor_id_invalido_se_rechaza(crear):
    with pytest.raises(ErrorDeValidacion):
        crear(sensor_id="no-es-uuid")


@pytest.mark.parametrize("crear", [humedad, ambiente])
def test_una_region_invalida_se_rechaza(crear):
    with pytest.raises(ValorFueraDeRango):
        crear(region_id=4)


# --- LecturaHumedad --------------------------------------------------------


def test_humedad_valida():
    lectura = humedad()
    assert lectura.humedad_suelo_pct == 45.5


@pytest.mark.parametrize("valor", [0, 100, "45,5", "45.5", 0.0])
def test_humedad_acepta_los_bordes_y_texto_numerico(valor):
    assert LecturaHumedad(humedad_suelo_pct=valor, **comunes())


@pytest.mark.parametrize("valor", [-0.1, 100.1, 180, -5])
def test_humedad_fuera_de_rango_lanza_su_excepcion(valor):
    with pytest.raises(LecturaFueraDeRango) as error:
        LecturaHumedad(humedad_suelo_pct=valor, **comunes())
    assert error.value.campo == "humedad del suelo"
    assert error.value.valor == valor


@pytest.mark.parametrize("valor", ["mucha", None, True, float("nan")])
def test_humedad_con_un_dato_que_no_es_numero(valor):
    with pytest.raises(TipoDeDatoInvalido):
        LecturaHumedad(humedad_suelo_pct=valor, **comunes())


def test_la_humedad_no_se_puede_cambiar():
    with pytest.raises(AttributeError):
        humedad().humedad_suelo_pct = 50


# --- LecturaAmbiente -------------------------------------------------------


def test_ambiente_valida():
    lectura = ambiente()
    assert lectura.temperatura_c == 22.5
    assert lectura.humedad_relativa_pct == 60


@pytest.mark.parametrize("valor", [-20, 60, 0])
def test_temperatura_acepta_los_bordes(valor):
    assert LecturaAmbiente(
        temperatura_c=valor, humedad_relativa_pct=50, **comunes()
    )


@pytest.mark.parametrize("valor", [-20.1, 60.1, 200, -90])
def test_temperatura_fuera_de_rango_lanza_su_excepcion(valor):
    with pytest.raises(LecturaFueraDeRango) as error:
        LecturaAmbiente(
            temperatura_c=valor, humedad_relativa_pct=50, **comunes()
        )
    assert error.value.campo == "temperatura"


@pytest.mark.parametrize("valor", [-1, 100.5, 250])
def test_humedad_relativa_fuera_de_rango_lanza_su_excepcion(valor):
    with pytest.raises(LecturaFueraDeRango) as error:
        LecturaAmbiente(
            temperatura_c=20, humedad_relativa_pct=valor, **comunes()
        )
    assert error.value.campo == "humedad relativa"


def test_ambiente_con_un_dato_que_no_es_numero():
    with pytest.raises(TipoDeDatoInvalido):
        LecturaAmbiente(
            temperatura_c="caliente", humedad_relativa_pct=50, **comunes()
        )


def test_ambiente_no_se_puede_modificar():
    lectura = ambiente()
    with pytest.raises(AttributeError):
        lectura.temperatura_c = 30
    with pytest.raises(AttributeError):
        lectura.humedad_relativa_pct = 30


# --- polimorfismo ----------------------------------------------------------


def test_cada_tipo_responde_distinto_al_mismo_mensaje():
    lecturas: list[LecturaSensor] = [humedad(), ambiente()]
    assert [x.humedad_para_planta() for x in lecturas] == [45.5, None]
    assert [x.resumen() for x in lecturas] == [
        "Humedad del suelo: 45.5 %",
        "Temperatura: 22.5 °C, humedad relativa: 60 %",
    ]
    assert [x.tipo for x in lecturas] == ["humedad", "ambiente"]


def test_a_documento_de_humedad():
    assert humedad().a_documento() == {
        "sensor_id": SENSOR,
        "planta_id": PLANTA,
        "region_id": 2,
        "tipo": "humedad",
        "timestamp": AHORA - timedelta(minutes=5),
        "humedad_suelo_pct": 45.5,
    }


def test_a_documento_de_ambiente():
    documento = ambiente().a_documento()
    assert documento["tipo"] == "ambiente"
    assert documento["temperatura_c"] == 22.5
    assert documento["humedad_relativa_pct"] == 60
    assert "humedad_suelo_pct" not in documento


# --- desde_documento -------------------------------------------------------


@pytest.mark.parametrize("crear", [humedad, ambiente])
def test_ida_y_vuelta_por_documento(crear):
    original = crear()
    copia = LecturaSensor.desde_documento(original.a_documento())
    assert type(copia) is type(original)
    assert copia == original


def test_desde_documento_acepta_fechas_sin_zona_de_mongodb():
    documento = humedad().a_documento()
    documento["timestamp"] = documento["timestamp"].replace(tzinfo=None)
    lectura = LecturaSensor.desde_documento(documento)
    assert lectura.timestamp == AHORA - timedelta(minutes=5)


def test_desde_documento_con_tipo_desconocido():
    documento = humedad().a_documento()
    documento["tipo"] = "luz"
    with pytest.raises(OpcionNoPermitida):
        LecturaSensor.desde_documento(documento)


def test_desde_documento_sin_tipo():
    documento = humedad().a_documento()
    del documento["tipo"]
    with pytest.raises(OpcionNoPermitida):
        LecturaSensor.desde_documento(documento)


@pytest.mark.parametrize("campo", ["sensor_id", "planta_id", "timestamp"])
def test_desde_documento_sin_un_dato_comun(campo):
    documento = humedad().a_documento()
    del documento[campo]
    with pytest.raises(CampoVacio):
        LecturaSensor.desde_documento(documento)


def test_desde_documento_sin_la_medida():
    documento = humedad().a_documento()
    del documento["humedad_suelo_pct"]
    with pytest.raises(CampoVacio):
        LecturaSensor.desde_documento(documento)


def test_desde_documento_ambiente_sin_una_medida():
    documento = ambiente().a_documento()
    del documento["temperatura_c"]
    with pytest.raises(CampoVacio):
        LecturaSensor.desde_documento(documento)


def test_desde_documento_con_una_lectura_fuera_de_rango():
    documento = humedad().a_documento()
    documento["humedad_suelo_pct"] = 500
    with pytest.raises(LecturaFueraDeRango):
        LecturaSensor.desde_documento(documento)


# --- igualdad y representación --------------------------------------------


def test_dos_lecturas_iguales_son_iguales_y_con_el_mismo_hash():
    assert humedad() == humedad()
    assert hash(humedad()) == hash(humedad())
    assert len({humedad(), humedad()}) == 1


def test_lecturas_distintas_no_son_iguales():
    assert humedad() != LecturaHumedad(humedad_suelo_pct=50, **comunes())
    assert humedad() != ambiente()
    assert humedad() != "algo"


def test_repr_muestra_el_tipo_y_el_sensor():
    texto = repr(humedad())
    assert texto.startswith("LecturaHumedad(")
    assert SENSOR in texto
