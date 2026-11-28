"""Escenarios completos del dominio (B5).

Aquí no se prueba cada regla por separado, sino que las clases funcionen
juntas como lo hará la API: una planta recibe lecturas de un sensor, una
planta inactiva no puede regarse, un error no deja un objeto a medias, etc.
"""

import math

import pytest

from plantas.dominio.excepciones import (
    ErrorDeInfraestructura,
    ErrorDeNegocio,
    ErrorDeValidacion,
    ErrorPlantas,
    LecturaFueraDeRango,
    PlantaInactiva,
)
from plantas.dominio.lecturas import LecturaSensor
from plantas.dominio.validaciones import (
    ResultadoLecturas,
    procesar_lecturas_humedad,
)
from tests.fabricas import (
    AHORA,
    HASH_DE_MENTIRA,
    MINUTO,
    PLANTA_ID,
    USUARIO_ID,
    hacer_cuidado,
    hacer_especie,
    hacer_lectura_ambiente,
    hacer_lectura_humedad,
    hacer_planta,
    hacer_riego,
    hacer_usuario,
)

# --- sensores opcionales ---------------------------------------------------


def test_una_planta_sin_sensor_funciona_sin_datos_de_humedad():
    planta = hacer_planta()
    assert planta.tiene_sensor_humedad is False
    assert planta.humedad_actual is None
    assert planta.fecha_ultima_lectura is None
    assert planta.esta_activa
    planta.verificar_activa()
    assert hacer_riego(cantidad_ml=300).es_riego


def test_una_lectura_de_humedad_actualiza_la_planta():
    planta = hacer_planta()
    planta.marcar_sensor_humedad(True)
    lectura = hacer_lectura_humedad(humedad_suelo_pct=35)
    planta.registrar_lectura_humedad(
        lectura.humedad_para_planta(), lectura.timestamp, AHORA
    )
    assert planta.tiene_sensor_humedad is True
    assert planta.humedad_actual == 35
    assert planta.fecha_ultima_lectura == lectura.timestamp


def test_una_lectura_ambiente_no_toca_la_humedad_de_la_planta():
    planta = hacer_planta()
    lectura = hacer_lectura_ambiente()
    assert lectura.humedad_para_planta() is None
    assert planta.humedad_actual is None


def test_la_humedad_leida_se_compara_con_el_rango_de_la_especie():
    especie = hacer_especie(humedad_ideal_min=40, humedad_ideal_max=70)
    planta = hacer_planta()
    estados = []
    for humedad in (20, 40, 55, 70, 95):
        lectura = hacer_lectura_humedad(humedad_suelo_pct=humedad)
        planta.registrar_lectura_humedad(
            lectura.humedad_para_planta(), lectura.timestamp, AHORA
        )
        estados.append(especie.humedad_en_rango(planta.humedad_actual))
    assert estados == [False, True, True, True, False]


def test_la_ultima_lectura_reemplaza_a_la_anterior():
    planta = hacer_planta()
    planta.registrar_lectura_humedad(30, AHORA - 2 * MINUTO, AHORA)
    planta.registrar_lectura_humedad(80, AHORA - MINUTO, AHORA)
    assert planta.humedad_actual == 80
    assert planta.fecha_ultima_lectura == AHORA - MINUTO


def test_marcar_o_quitar_el_sensor_no_borra_la_ultima_lectura():
    planta = hacer_planta()
    planta.marcar_sensor_humedad(True)
    planta.registrar_lectura_humedad(50, AHORA - MINUTO, AHORA)
    planta.marcar_sensor_humedad(False)
    assert planta.tiene_sensor_humedad is False
    assert planta.humedad_actual == 50


def test_la_humedad_y_su_fecha_van_juntas_o_ninguna():
    with pytest.raises(ErrorDeValidacion):
        hacer_planta(humedad_actual=50)
    with pytest.raises(ErrorDeValidacion):
        hacer_planta(fecha_ultima_lectura=AHORA - MINUTO)
    assert hacer_planta().humedad_actual is None


@pytest.mark.parametrize(
    "lectura", [hacer_lectura_humedad, hacer_lectura_ambiente]
)
def test_una_lectura_guardada_y_leida_de_nuevo_es_la_misma(lectura):
    original = lectura()
    documento = original.a_documento()
    documento["timestamp"] = documento["timestamp"].replace(tzinfo=None)
    leida = LecturaSensor.desde_documento(documento)
    assert leida == original
    assert leida.a_documento() == original.a_documento()


def test_un_lote_mixto_de_lecturas_no_se_detiene_en_la_primera_falla():
    documentos = [
        hacer_lectura_humedad(humedad_suelo_pct=40).a_documento(),
        {**hacer_lectura_humedad().a_documento(), "humedad_suelo_pct": 180},
        hacer_lectura_ambiente().a_documento(),
        {**hacer_lectura_ambiente().a_documento(), "tipo": "luz"},
    ]
    buenas, malas = [], []
    for documento in documentos:
        try:
            buenas.append(LecturaSensor.desde_documento(documento))
        except ErrorDeValidacion as error:
            malas.append(type(error).__name__)
    assert [type(x).__name__ for x in buenas] == [
        "LecturaHumedad",
        "LecturaAmbiente",
    ]
    assert malas == ["LecturaFueraDeRango", "OpcionNoPermitida"]


# --- plantas inactivas y cuidados ------------------------------------------


@pytest.mark.parametrize("estatus", ["fallecida", "regalada"])
def test_una_planta_que_ya_no_esta_activa_no_se_puede_regar(estatus):
    planta = hacer_planta(estatus=estatus)
    assert not planta.esta_activa
    with pytest.raises(PlantaInactiva) as error:
        planta.verificar_activa()
    assert error.value.planta_id == PLANTA_ID
    assert error.value.estatus == estatus
    assert isinstance(error.value, ErrorDeNegocio)


def test_una_planta_puede_volver_a_estar_activa():
    planta = hacer_planta(estatus="fallecida")
    planta.cambiar_estatus("activa")
    planta.verificar_activa()


def test_solo_el_riego_lleva_cantidad_de_agua():
    assert hacer_riego(cantidad_ml=250).cantidad_ml == 250
    assert hacer_riego().cantidad_ml is None
    for tipo in ("fertilizado", "poda", "trasplante", "otro"):
        assert hacer_cuidado(tipo=tipo).cantidad_ml is None
        with pytest.raises(ErrorDeValidacion):
            hacer_cuidado(tipo=tipo, cantidad_ml=100)


def test_un_cuidado_no_se_puede_modificar_despues_de_creado():
    cuidado = hacer_riego(cantidad_ml=100)
    for campo in ("tipo", "cantidad_ml", "fecha_hora", "notas", "planta_id"):
        with pytest.raises(AttributeError):
            setattr(cuidado, campo, None)


# --- un error no deja el objeto a medias -----------------------------------

# (fábrica, campo, valor inválido)
CAMBIOS_INVALIDOS = [
    (hacer_usuario, "nombre", ""),
    (hacer_usuario, "apellidos", "x" * 121),
    (hacer_usuario, "correo", "sin-arroba"),
    (hacer_usuario, "estado_id", 33),
    (hacer_usuario, "rol", "superadmin"),
    (hacer_planta, "apodo", "   "),
    (hacer_planta, "tipo_espacio", "sotano"),
    (hacer_planta, "ubicacion_descripcion", "x" * 101),
    (hacer_especie, "nombre_comun", None),
    (hacer_especie, "frecuencia_riego_dias", 0),
    (hacer_especie, "luz", "neon"),
    (hacer_especie, "fuente", ""),
    (hacer_especie, "cuidados", "x" * 5001),
]


@pytest.mark.parametrize(
    ("fabrica", "campo", "invalido"),
    CAMBIOS_INVALIDOS,
    ids=[f"{f.__name__}-{c}" for f, c, _ in CAMBIOS_INVALIDOS],
)
def test_un_cambio_invalido_deja_el_valor_anterior(fabrica, campo, invalido):
    objeto = fabrica()
    antes = getattr(objeto, campo)
    with pytest.raises(ErrorDeValidacion):
        setattr(objeto, campo, invalido)
    assert getattr(objeto, campo) == antes


def test_una_lectura_con_la_fecha_mala_no_cambia_la_humedad():
    planta = hacer_planta()
    planta.registrar_lectura_humedad(40, AHORA - MINUTO, AHORA)
    with pytest.raises(ErrorDeValidacion):
        planta.registrar_lectura_humedad(90, AHORA + MINUTO, AHORA)
    assert (planta.humedad_actual, planta.fecha_ultima_lectura) == (
        40,
        AHORA - MINUTO,
    )


def test_una_lectura_con_la_humedad_mala_no_cambia_la_fecha():
    planta = hacer_planta()
    planta.registrar_lectura_humedad(40, AHORA - 2 * MINUTO, AHORA)
    with pytest.raises(ErrorDeValidacion):
        planta.registrar_lectura_humedad(101, AHORA - MINUTO, AHORA)
    assert planta.fecha_ultima_lectura == AHORA - 2 * MINUTO


def test_el_estatus_invalido_no_cambia_el_estatus():
    planta = hacer_planta()
    with pytest.raises(ErrorDeValidacion):
        planta.cambiar_estatus("vendida")
    assert planta.estatus == "activa"


def test_los_datos_de_solo_lectura_no_se_pueden_reasignar():
    usuario, planta, especie = hacer_usuario(), hacer_planta(), hacer_especie()
    casos = [
        (usuario, "usuario_id"),
        (usuario, "region_id"),
        (usuario, "password_hash"),
        (planta, "planta_id"),
        (planta, "region_id"),
        (planta, "usuario_id"),
        (planta, "humedad_actual"),
        (planta, "estatus"),
        (especie, "nombre_cientifico"),
        (especie, "humedad_ideal_min"),
        (especie, "temp_max"),
    ]
    for objeto, campo in casos:
        with pytest.raises(AttributeError):
            setattr(objeto, campo, "otro")


# --- identidad e igualdad --------------------------------------------------


def test_dos_objetos_con_los_mismos_ids_son_el_mismo():
    assert hacer_planta(apodo="Fiona") == hacer_planta(apodo="Otro nombre")
    assert hacer_usuario(nombre="Ana") == hacer_usuario(nombre="Beatriz")
    assert len({hacer_planta(), hacer_planta(apodo="Otro")}) == 1


def test_la_region_forma_parte_de_la_identidad():
    assert hacer_planta(region_id=1) != hacer_planta(region_id=2)
    assert hacer_usuario(region_id=1) != hacer_usuario(region_id=3)
    assert hacer_cuidado(region_id=1) != hacer_cuidado(region_id=2)


def test_objetos_de_clases_distintas_nunca_son_iguales():
    objetos = [
        hacer_usuario(),
        hacer_planta(),
        hacer_cuidado(),
        hacer_especie(),
        hacer_lectura_humedad(),
    ]
    for i, uno in enumerate(objetos):
        assert uno != "texto"
        for otro in objetos[i + 1 :]:
            assert uno != otro


def test_la_especie_se_identifica_por_su_nombre_cientifico_en_minusculas():
    a = hacer_especie(nombre_cientifico="Ficus lyrata")
    b = hacer_especie(nombre_cientifico="  FICUS LYRATA ", nombre_comun="Otro")
    assert a == b
    assert hash(a) == hash(b)
    assert a != hacer_especie(nombre_cientifico="Ficus elastica")


def test_las_lecturas_con_otra_medida_no_son_iguales():
    assert hacer_lectura_humedad(
        humedad_suelo_pct=40
    ) != hacer_lectura_humedad(humedad_suelo_pct=41)
    assert hacer_lectura_ambiente(temperatura_c=20) != hacer_lectura_ambiente(
        temperatura_c=21
    )


# --- datos sensibles y errores ---------------------------------------------


def test_el_repr_del_usuario_no_muestra_datos_personales_ni_el_hash():
    usuario = hacer_usuario(
        nombre="Ana", apellidos="López Pérez", correo="ana@example.com"
    )
    texto = repr(usuario) + str(usuario)
    for secreto in ("ana@example.com", HASH_DE_MENTIRA, "Ana", "López"):
        assert secreto not in texto
    assert str(USUARIO_ID) in texto


def test_el_repr_de_los_demas_objetos_no_muestra_notas_ni_ubicacion():
    assert "Fiona" not in repr(hacer_planta(ubicacion_descripcion="mi casa"))
    assert "mi casa" not in repr(hacer_planta(ubicacion_descripcion="mi casa"))
    assert "secreto" not in repr(hacer_cuidado(notas="secreto"))


def test_el_mensaje_de_un_error_dice_que_campo_fallo():
    with pytest.raises(LecturaFueraDeRango) as error:
        hacer_lectura_humedad(humedad_suelo_pct=101)
    assert "humedad del suelo" in str(error.value)
    assert error.value.campo == "humedad del suelo"
    assert error.value.valor == 101


def test_todos_los_errores_del_dominio_se_atrapan_con_la_base():
    llamadas = [
        lambda: hacer_planta(apodo=""),
        lambda: hacer_usuario(correo="x"),
        lambda: hacer_lectura_humedad(humedad_suelo_pct=-1),
        lambda: hacer_planta(estatus="fallecida").verificar_activa(),
        lambda: LecturaSensor.desde_documento({}),
    ]
    for llamada in llamadas:
        with pytest.raises(ErrorPlantas):
            llamada()


def test_los_errores_de_validacion_no_son_de_negocio_ni_de_infraestructura():
    with pytest.raises(ErrorDeValidacion) as error:
        hacer_planta(apodo="")
    assert not isinstance(error.value, ErrorDeNegocio)
    assert not isinstance(error.value, ErrorDeInfraestructura)


# --- lotes de humedad (try / except / else / finally) ----------------------


def test_un_lote_vacio_no_procesa_nada():
    assert procesar_lecturas_humedad([]) == ResultadoLecturas()


def test_un_lote_de_solo_lecturas_malas_las_cuenta_todas():
    resultado = procesar_lecturas_humedad([-1, 101, "x", None, math.nan])
    assert resultado.validas == []
    assert [posicion for posicion, _ in resultado.errores] == [1, 2, 3, 4, 5]
    assert resultado.procesadas == 5


def test_un_lote_con_los_bordes_acepta_el_0_y_el_100():
    resultado = procesar_lecturas_humedad([0, "100", "45,5", 100.0])
    assert resultado.validas == [0, 100, 45.5, 100]
    assert resultado.errores == []


def test_cada_lectura_se_cuenta_aunque_falle():
    resultado = procesar_lecturas_humedad(iter([10, "malo", 20, 500, 30]))
    assert resultado.validas == [10, 20, 30]
    assert [posicion for posicion, _ in resultado.errores] == [2, 4]
    assert resultado.procesadas == 5
    assert resultado.procesadas == len(resultado.validas) + len(
        resultado.errores
    )


def test_el_lote_acepta_cualquier_iterable_y_solo_atrapa_errores_propios():
    assert procesar_lecturas_humedad(x for x in (1, 2, 3)).procesadas == 3

    def generador_roto():
        yield 10
        raise RuntimeError("el archivo se cerró")

    with pytest.raises(RuntimeError):
        procesar_lecturas_humedad(generador_roto())
