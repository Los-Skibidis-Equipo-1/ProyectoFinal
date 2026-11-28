"""Casos límite de los textos, correos, identificadores, opciones y fechas.

Complementa a ``test_limites.py`` (que cubre los números): aquí se prueba
el largo máximo de cada texto, los textos vacíos, los UUID mal formados, cada
opción de cada catálogo y el borde exacto de las fechas.
"""

from datetime import UTC, date, datetime, timedelta, timezone
from uuid import UUID

import pytest

from plantas.dominio import catalogos
from plantas.dominio.excepciones import (
    CampoVacio,
    FechaInvalida,
    FormatoInvalido,
    OpcionNoPermitida,
    TipoDeDatoInvalido,
    ValorFueraDeRango,
)
from plantas.dominio.lecturas import LecturaSensor
from tests.fabricas import (
    AHORA,
    HOY,
    USUARIO_ID,
    hacer_cuidado,
    hacer_especie,
    hacer_lectura_ambiente,
    hacer_lectura_humedad,
    hacer_planta,
    hacer_usuario,
)

# --- largo máximo de los textos --------------------------------------------

# (nombre, fábrica, campo, largo máximo, ¿obligatorio?)
TEXTOS = [
    ("usuario.nombre", hacer_usuario, "nombre", 80, True),
    ("usuario.apellidos", hacer_usuario, "apellidos", 120, True),
    ("planta.apodo", hacer_planta, "apodo", 60, True),
    (
        "planta.ubicacion",
        hacer_planta,
        "ubicacion_descripcion",
        100,
        False,
    ),
    ("cuidado.notas", hacer_cuidado, "notas", 500, False),
    ("especie.nombre_comun", hacer_especie, "nombre_comun", 80, True),
    (
        "especie.nombre_cientifico",
        hacer_especie,
        "nombre_cientifico",
        120,
        True,
    ),
    ("especie.cuidados", hacer_especie, "cuidados", 5000, False),
]
OBLIGATORIOS = [pytest.param(f, c, m, id=n) for n, f, c, m, o in TEXTOS if o]
OPCIONALES = [pytest.param(f, c, m, id=n) for n, f, c, m, o in TEXTOS if not o]
TODOS = [pytest.param(f, c, m, id=n) for n, f, c, m, _ in TEXTOS]


@pytest.mark.parametrize(("fabrica", "campo", "maximo"), TODOS)
def test_un_texto_del_largo_maximo_se_acepta(fabrica, campo, maximo):
    objeto = fabrica(**{campo: "x" * maximo})
    assert getattr(objeto, campo) == "x" * maximo


@pytest.mark.parametrize(("fabrica", "campo", "maximo"), TODOS)
def test_un_caracter_de_mas_se_rechaza(fabrica, campo, maximo):
    with pytest.raises(ValorFueraDeRango):
        fabrica(**{campo: "x" * (maximo + 1)})


@pytest.mark.parametrize(("fabrica", "campo", "maximo"), TODOS)
def test_los_espacios_de_los_extremos_no_cuentan_para_el_largo(
    fabrica, campo, maximo
):
    objeto = fabrica(**{campo: f"  {'x' * maximo}\n"})
    assert getattr(objeto, campo) == "x" * maximo


@pytest.mark.parametrize(("fabrica", "campo", "maximo"), TODOS)
def test_cuenta_caracteres_y_no_bytes(fabrica, campo, maximo):
    texto = "ñ" * maximo
    assert getattr(fabrica(**{campo: texto}), campo) == texto
    with pytest.raises(ValorFueraDeRango):
        fabrica(**{campo: texto + "á"})


@pytest.mark.parametrize(("fabrica", "campo", "maximo"), TODOS)
@pytest.mark.parametrize("valor", [123, 4.5, True, ["x"], b"x"], ids=repr)
def test_un_dato_que_no_es_texto_se_rechaza(fabrica, campo, maximo, valor):
    with pytest.raises(TipoDeDatoInvalido):
        fabrica(**{campo: valor})


@pytest.mark.parametrize(("fabrica", "campo", "maximo"), OBLIGATORIOS)
@pytest.mark.parametrize("valor", ["", "   ", "\t\n"], ids=repr)
def test_un_texto_obligatorio_no_puede_estar_vacio(
    fabrica, campo, maximo, valor
):
    with pytest.raises(CampoVacio):
        fabrica(**{campo: valor})


@pytest.mark.parametrize(("fabrica", "campo", "maximo"), OBLIGATORIOS)
def test_un_texto_obligatorio_no_puede_ser_none(fabrica, campo, maximo):
    with pytest.raises(TipoDeDatoInvalido):
        fabrica(**{campo: None})


@pytest.mark.parametrize(("fabrica", "campo", "maximo"), OPCIONALES)
@pytest.mark.parametrize("valor", [None, "", "   ", "\t\n"], ids=repr)
def test_un_texto_opcional_vacio_se_guarda_como_none(
    fabrica, campo, maximo, valor
):
    assert getattr(fabrica(**{campo: valor}), campo) is None


@pytest.mark.parametrize(
    ("fabrica", "campo"),
    [
        (hacer_usuario, "nombre"),
        (hacer_usuario, "apellidos"),
        (hacer_planta, "apodo"),
        (hacer_planta, "ubicacion_descripcion"),
        (hacer_especie, "nombre_comun"),
        (hacer_especie, "cuidados"),
        (hacer_especie, "fuente"),
    ],
)
def test_los_textos_editables_se_validan_igual_al_cambiarlos(fabrica, campo):
    objeto = fabrica()
    setattr(objeto, campo, "  Nuevo valor  ")
    assert getattr(objeto, campo) == "Nuevo valor"
    with pytest.raises(TipoDeDatoInvalido):
        setattr(objeto, campo, 123)
    assert getattr(objeto, campo) == "Nuevo valor"


def test_la_fuente_de_la_especie_es_obligatoria_y_sin_largo_maximo():
    assert hacer_especie(fuente="f" * 10_000).fuente == "f" * 10_000
    with pytest.raises(CampoVacio):
        hacer_especie(fuente="  ")


# --- correo y hash de contraseña -------------------------------------------


def _correo_de_largo(largo):
    resto = "@b.co"
    return "a" * (largo - len(resto)) + resto


def test_el_correo_de_254_caracteres_se_acepta_y_el_de_255_no():
    assert len(hacer_usuario(correo=_correo_de_largo(254)).correo) == 254
    with pytest.raises(FormatoInvalido):
        hacer_usuario(correo=_correo_de_largo(255))


@pytest.mark.parametrize(
    "correo", ["a@b.c", "a.b+etiqueta@sub.ejemplo.com", "ñandú@ejemplo.mx"]
)
def test_correos_con_forma_valida(correo):
    assert hacer_usuario(correo=correo).correo == correo


@pytest.mark.parametrize(
    "correo",
    ["a", "a@", "@b.c", "a@b", "a b@c.d", "a@@b.c", "a@b.", "a@.c", "a@b c.d"],
)
def test_correos_sin_forma_de_correo(correo):
    with pytest.raises(FormatoInvalido) as error:
        hacer_usuario(correo=correo)
    assert error.value.campo == "correo"


def test_el_correo_se_guarda_en_minusculas_y_sin_espacios():
    assert hacer_usuario(correo="  ANA@Example.COM \n").correo == (
        "ana@example.com"
    )


def test_un_correo_vacio_o_que_no_es_texto():
    with pytest.raises(CampoVacio):
        hacer_usuario(correo="  ")
    with pytest.raises(TipoDeDatoInvalido):
        hacer_usuario(correo=None)


def test_el_hash_de_32_caracteres_se_acepta_y_el_de_31_no():
    assert hacer_usuario(password_hash="h" * 32).password_hash == "h" * 32
    with pytest.raises(FormatoInvalido):
        hacer_usuario(password_hash="h" * 31)


@pytest.mark.parametrize("valor", [None, 123, "", b"h" * 64], ids=repr)
def test_un_hash_que_no_es_texto_o_esta_vacio(valor):
    with pytest.raises(FormatoInvalido):
        hacer_usuario(password_hash=valor)


def test_el_error_del_hash_no_guarda_el_valor():
    with pytest.raises(FormatoInvalido) as error:
        hacer_usuario(password_hash="corto")
    assert error.value.valor is None
    assert "corto" not in str(error.value)


def test_cambiar_el_hash_valida_igual_y_conserva_el_anterior_si_falla():
    usuario = hacer_usuario()
    usuario.cambiar_password_hash("n" * 40)
    with pytest.raises(FormatoInvalido):
        usuario.cambiar_password_hash("corto")
    assert usuario.password_hash == "n" * 40


# --- identificadores UUID --------------------------------------------------

IDENTIFICADORES = [
    pytest.param(lambda v: hacer_usuario(usuario_id=v), id="usuario_id"),
    pytest.param(lambda v: hacer_planta(planta_id=v), id="planta.planta_id"),
    pytest.param(lambda v: hacer_planta(usuario_id=v), id="planta.usuario_id"),
    pytest.param(lambda v: hacer_cuidado(planta_id=v), id="cuidado.planta_id"),
    pytest.param(lambda v: hacer_cuidado(cuidado_id=v), id="cuidado_id"),
    pytest.param(
        lambda v: hacer_lectura_humedad(sensor_id=v), id="lectura.sensor_id"
    ),
    pytest.param(
        lambda v: hacer_lectura_ambiente(planta_id=v), id="lectura.planta_id"
    ),
]


@pytest.mark.parametrize("crear", IDENTIFICADORES)
def test_un_uuid_se_acepta_como_objeto_o_como_texto(crear):
    crear(USUARIO_ID)
    crear(str(USUARIO_ID))
    crear(f"  {str(USUARIO_ID).upper()}  ")


@pytest.mark.parametrize("crear", IDENTIFICADORES)
@pytest.mark.parametrize(
    "valor",
    ["", "123", "no-es-uuid", "1111-1111", "g" * 36, 123, ["x"], b"x"],
    ids=repr,
)
def test_un_identificador_mal_formado_se_rechaza(crear, valor):
    with pytest.raises(TipoDeDatoInvalido):
        crear(valor)


def test_el_uuid_en_mayusculas_es_el_mismo_que_en_minusculas():
    a = hacer_usuario(usuario_id=str(USUARIO_ID).upper())
    b = hacer_usuario(usuario_id=str(USUARIO_ID))
    assert a.usuario_id == b.usuario_id == UUID(str(USUARIO_ID))
    assert a == b


def test_sin_id_se_genera_uno_distinto_cada_vez():
    ids = {
        hacer_usuario(usuario_id=None).usuario_id,
        hacer_usuario(usuario_id=None).usuario_id,
    }
    assert len(ids) == 2
    assert len({hacer_planta(planta_id=None).planta_id for _ in range(5)}) == 5
    assert (
        len({hacer_cuidado(cuidado_id=None).cuidado_id for _ in range(5)}) == 5
    )


# --- opciones de los catálogos ---------------------------------------------

# (nombre, catálogo, función que intenta usar una opción)
OPCIONES = [
    (
        "tipo_espacio",
        catalogos.TIPOS_ESPACIO,
        lambda v: hacer_planta(tipo_espacio=v),
    ),
    ("estatus", catalogos.ESTATUS_PLANTA, lambda v: hacer_planta(estatus=v)),
    (
        "tipo de cuidado",
        catalogos.TIPOS_CUIDADO,
        lambda v: hacer_cuidado(tipo=v),
    ),
    ("rol", catalogos.ROLES, lambda v: hacer_usuario(rol=v)),
    ("luz", catalogos.NIVELES_LUZ, lambda v: hacer_especie(luz=v)),
]
TODAS_LAS_OPCIONES = [
    pytest.param(usar, opcion, id=f"{nombre}-{opcion}")
    for nombre, catalogo, usar in OPCIONES
    for opcion in catalogo
]
CAMPOS_CON_OPCIONES = [
    pytest.param(usar, id=nombre) for nombre, _, usar in OPCIONES
]


@pytest.mark.parametrize(("usar", "opcion"), TODAS_LAS_OPCIONES)
def test_cada_opcion_del_catalogo_se_acepta(usar, opcion):
    usar(opcion)
    usar(f"  {opcion.upper()} ")


@pytest.mark.parametrize("usar", CAMPOS_CON_OPCIONES)
@pytest.mark.parametrize(
    "valor", ["xyz", "casas", "activ", "0", "casa,patio"], ids=repr
)
def test_algo_que_no_es_una_opcion_se_rechaza(usar, valor):
    with pytest.raises(OpcionNoPermitida):
        usar(valor)


@pytest.mark.parametrize("usar", CAMPOS_CON_OPCIONES)
def test_una_opcion_vacia_o_que_no_es_texto(usar):
    with pytest.raises(CampoVacio):
        usar("")
    with pytest.raises(TipoDeDatoInvalido):
        usar(None)
    with pytest.raises(TipoDeDatoInvalido):
        usar(1)


def test_el_error_de_opcion_dice_cuales_son_las_permitidas():
    with pytest.raises(OpcionNoPermitida) as error:
        hacer_planta(tipo_espacio="sotano")
    for opcion in catalogos.TIPOS_ESPACIO:
        assert opcion in str(error.value)


@pytest.mark.parametrize("tipo", ["luz", "", None, "HUMEDAD2"], ids=repr)
def test_un_tipo_de_lectura_desconocido_no_se_acepta(tipo):
    documento = hacer_lectura_humedad().a_documento()
    documento["tipo"] = tipo
    with pytest.raises(OpcionNoPermitida):
        LecturaSensor.desde_documento(documento)


# --- fechas: el borde exacto -----------------------------------------------

UN_MICROSEGUNDO = timedelta(microseconds=1)
MEXICO = timezone(timedelta(hours=-6))

FECHAS_CON_HORA = [
    pytest.param(
        lambda v: hacer_lectura_humedad(timestamp=v), id="lectura.timestamp"
    ),
    pytest.param(
        lambda v: hacer_cuidado(fecha_hora=v), id="cuidado.fecha_hora"
    ),
    pytest.param(
        lambda v: hacer_planta().registrar_lectura_humedad(50, v, AHORA),
        id="planta.registrar_lectura",
    ),
    pytest.param(
        lambda v: hacer_planta(humedad_actual=50, fecha_ultima_lectura=v),
        id="planta.fecha_ultima_lectura",
    ),
]


@pytest.mark.parametrize("usar", FECHAS_CON_HORA)
def test_la_fecha_igual_a_ahora_se_acepta_y_un_microsegundo_despues_no(usar):
    usar(AHORA)
    usar(AHORA - UN_MICROSEGUNDO)
    with pytest.raises(FechaInvalida):
        usar(AHORA + UN_MICROSEGUNDO)


@pytest.mark.parametrize("usar", FECHAS_CON_HORA)
def test_la_fecha_sin_zona_horaria_se_rechaza(usar):
    with pytest.raises(FechaInvalida):
        usar(datetime(2026, 11, 27, 11, 0))


@pytest.mark.parametrize("usar", FECHAS_CON_HORA)
@pytest.mark.parametrize(
    "valor", ["2026-11-27T11:00:00+00:00", 1_795_000_000, HOY, [], object()]
)
def test_lo_que_no_es_datetime_se_rechaza(usar, valor):
    with pytest.raises(FechaInvalida):
        usar(valor)


@pytest.mark.parametrize("usar", FECHAS_CON_HORA)
def test_la_comparacion_considera_la_zona_horaria(usar):
    # 05:59 en México (UTC-6) son las 11:59 UTC, antes de las 12:00 UTC.
    usar(datetime(2026, 11, 27, 5, 59, tzinfo=MEXICO))
    # 06:01 en México son las 12:01 UTC, un minuto en el futuro.
    with pytest.raises(FechaInvalida):
        usar(datetime(2026, 11, 27, 6, 1, tzinfo=MEXICO))


def test_sin_fecha_el_cuidado_y_la_lectura_usan_la_hora_actual():
    antes = datetime.now(UTC)
    cuidado = hacer_cuidado(fecha_hora=None, ahora=None)
    lectura = hacer_lectura_humedad(timestamp=None, ahora=None)
    despues = datetime.now(UTC)
    assert antes <= cuidado.fecha_hora <= despues
    assert antes <= lectura.timestamp <= despues


def test_la_fecha_de_adquisicion_hoy_se_acepta_y_manana_no():
    assert hacer_planta(fecha_adquisicion=HOY).fecha_adquisicion == HOY
    ayer = HOY - timedelta(days=1)
    assert hacer_planta(fecha_adquisicion=ayer).fecha_adquisicion == ayer
    with pytest.raises(FechaInvalida):
        hacer_planta(fecha_adquisicion=HOY + timedelta(days=1))


def test_la_fecha_de_adquisicion_es_opcional():
    assert hacer_planta(fecha_adquisicion=None).fecha_adquisicion is None


@pytest.mark.parametrize(
    "valor",
    [datetime(2026, 11, 1, tzinfo=UTC), "2026-11-01", 20261101, []],
    ids=repr,
)
def test_la_fecha_de_adquisicion_debe_ser_una_fecha_sin_hora(valor):
    with pytest.raises(FechaInvalida):
        hacer_planta(fecha_adquisicion=valor)


def test_fechas_muy_antiguas_son_validas():
    assert hacer_planta(fecha_adquisicion=date(1900, 1, 1))
    assert hacer_lectura_humedad(timestamp=datetime(2000, 1, 1, tzinfo=UTC))
