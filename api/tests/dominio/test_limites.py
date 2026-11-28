"""Casos límite de todos los rangos numéricos del dominio (B5).

Cada límite del esquema (humedad 0 a 100, temperatura -20 a 60, riego de 1 a
365 días, etc.) se prueba en **cada punto de entrada** donde se puede
capturar: la función de validación, el constructor y el método de cambio de
cada clase. Para cada uno se comprueba el valor mínimo, el máximo, un poco
por debajo y un poco por encima, los decimales y los datos que ni siquiera
son números.

Si alguien agrega un límite nuevo a ``catalogos.py`` sin darlo de alta aquí,
``test_todos_los_limites_del_catalogo_tienen_casos`` falla.
"""

import math

import pytest

from plantas.dominio import catalogos
from plantas.dominio.excepciones import (
    LecturaFueraDeRango,
    TipoDeDatoInvalido,
    ValorFueraDeRango,
)
from plantas.dominio.validaciones import (
    validar_cantidad_agua_ml,
    validar_estado_id,
    validar_frecuencia_riego_dias,
    validar_humedad,
    validar_region,
    validar_temperatura,
)
from tests.fabricas import (
    AHORA,
    MINUTO,
    hacer_cuidado,
    hacer_especie,
    hacer_lectura_ambiente,
    hacer_lectura_humedad,
    hacer_planta,
    hacer_riego,
    hacer_usuario,
)

# prefijo del catálogo: (mínimo, máximo, ¿solo enteros?)
LIMITES = {
    "HUMEDAD": (catalogos.HUMEDAD_MIN, catalogos.HUMEDAD_MAX, False),
    "TEMPERATURA": (
        catalogos.TEMPERATURA_MIN,
        catalogos.TEMPERATURA_MAX,
        False,
    ),
    "RIEGO_DIAS": (catalogos.RIEGO_DIAS_MIN, catalogos.RIEGO_DIAS_MAX, True),
    "CANTIDAD_RIEGO_ML": (
        catalogos.CANTIDAD_RIEGO_ML_MIN,
        catalogos.CANTIDAD_RIEGO_ML_MAX,
        True,
    ),
    "REGION": (catalogos.REGION_MIN, catalogos.REGION_MAX, True),
    "ESTADO_ID": (catalogos.ESTADO_ID_MIN, catalogos.ESTADO_ID_MAX, True),
}


# --- puntos de entrada: cada uno recibe un valor y lo intenta usar ---------


def _registrar_lectura_en_planta(valor):
    hacer_planta().registrar_lectura_humedad(valor, AHORA - MINUTO, AHORA)


def _planta_con_humedad(valor):
    hacer_planta(humedad_actual=valor, fecha_ultima_lectura=AHORA - MINUTO)


def _cambiar_frecuencia(valor):
    hacer_especie().frecuencia_riego_dias = valor


def _cambiar_estado_del_usuario(valor):
    hacer_usuario().estado_id = valor


# (prefijo, nombre del punto de entrada, función, excepción si está fuera)
PUERTAS = [
    ("HUMEDAD", "validar_humedad", validar_humedad, ValorFueraDeRango),
    (
        "HUMEDAD",
        "Planta.registrar_lectura_humedad",
        _registrar_lectura_en_planta,
        ValorFueraDeRango,
    ),
    (
        "HUMEDAD",
        "Planta(humedad_actual)",
        _planta_con_humedad,
        ValorFueraDeRango,
    ),
    (
        "HUMEDAD",
        "LecturaHumedad",
        lambda v: hacer_lectura_humedad(humedad_suelo_pct=v),
        LecturaFueraDeRango,
    ),
    (
        "HUMEDAD",
        "LecturaAmbiente(humedad_relativa)",
        lambda v: hacer_lectura_ambiente(humedad_relativa_pct=v),
        LecturaFueraDeRango,
    ),
    (
        "TEMPERATURA",
        "validar_temperatura",
        validar_temperatura,
        ValorFueraDeRango,
    ),
    (
        "TEMPERATURA",
        "LecturaAmbiente(temperatura)",
        lambda v: hacer_lectura_ambiente(temperatura_c=v),
        LecturaFueraDeRango,
    ),
    (
        "RIEGO_DIAS",
        "validar_frecuencia_riego_dias",
        validar_frecuencia_riego_dias,
        ValorFueraDeRango,
    ),
    (
        "RIEGO_DIAS",
        "Especie(frecuencia_riego_dias)",
        lambda v: hacer_especie(frecuencia_riego_dias=v),
        ValorFueraDeRango,
    ),
    (
        "RIEGO_DIAS",
        "Especie.frecuencia_riego_dias =",
        _cambiar_frecuencia,
        ValorFueraDeRango,
    ),
    (
        "CANTIDAD_RIEGO_ML",
        "validar_cantidad_agua_ml",
        validar_cantidad_agua_ml,
        ValorFueraDeRango,
    ),
    (
        "CANTIDAD_RIEGO_ML",
        "Cuidado.riego(cantidad_ml)",
        lambda v: hacer_riego(cantidad_ml=v),
        ValorFueraDeRango,
    ),
    ("REGION", "validar_region", validar_region, ValorFueraDeRango),
    (
        "REGION",
        "Usuario(region_id)",
        lambda v: hacer_usuario(region_id=v),
        ValorFueraDeRango,
    ),
    (
        "REGION",
        "Planta(region_id)",
        lambda v: hacer_planta(region_id=v),
        ValorFueraDeRango,
    ),
    (
        "REGION",
        "Cuidado(region_id)",
        lambda v: hacer_cuidado(region_id=v),
        ValorFueraDeRango,
    ),
    (
        "REGION",
        "LecturaHumedad(region_id)",
        lambda v: hacer_lectura_humedad(region_id=v),
        ValorFueraDeRango,
    ),
    ("ESTADO_ID", "validar_estado_id", validar_estado_id, ValorFueraDeRango),
    (
        "ESTADO_ID",
        "Usuario(estado_id)",
        lambda v: hacer_usuario(estado_id=v),
        ValorFueraDeRango,
    ),
    (
        "ESTADO_ID",
        "Usuario.estado_id =",
        _cambiar_estado_del_usuario,
        ValorFueraDeRango,
    ),
]

CASOS = [
    pytest.param(prefijo, usar, error, id=f"{prefijo}-{nombre}")
    for prefijo, nombre, usar, error in PUERTAS
]
CASOS_CON_DECIMALES_PERMITIDOS = [
    caso for caso in CASOS if not LIMITES[caso.values[0]][2]
]
CASOS_SOLO_ENTEROS = [caso for caso in CASOS if LIMITES[caso.values[0]][2]]

NO_NUMEROS = [
    "",
    "   ",
    "abc",
    "1,2,3",
    "12abc",
    True,
    False,
    math.nan,
    math.inf,
    -math.inf,
    [],
    {},
    (1,),
    object(),
]


def test_todos_los_limites_del_catalogo_tienen_casos():
    en_el_catalogo = {
        nombre.removesuffix("_MIN")
        for nombre in vars(catalogos)
        if nombre.endswith("_MIN")
    }
    assert en_el_catalogo == set(LIMITES)
    for prefijo in en_el_catalogo:
        assert hasattr(catalogos, f"{prefijo}_MAX")


def test_cada_limite_se_prueba_en_al_menos_un_punto_de_entrada():
    probados = {prefijo for prefijo, *_ in PUERTAS}
    assert probados == set(LIMITES)


@pytest.mark.parametrize(("prefijo", "usar", "error"), CASOS)
def test_el_minimo_y_el_maximo_se_aceptan(prefijo, usar, error):
    minimo, maximo, _ = LIMITES[prefijo]
    usar(minimo)
    usar(maximo)


@pytest.mark.parametrize(("prefijo", "usar", "error"), CASOS)
def test_justo_fuera_del_rango_se_rechaza(prefijo, usar, error):
    minimo, maximo, _ = LIMITES[prefijo]
    for valor in (minimo - 1, maximo + 1, minimo - 0.001, maximo + 0.001):
        with pytest.raises(error) as capturado:
            usar(valor)
        assert capturado.value.valor == valor


@pytest.mark.parametrize(("prefijo", "usar", "error"), CASOS)
def test_valores_enormes_se_rechazan(prefijo, usar, error):
    for valor in (10**9, -(10**9), 1e300, -1e300):
        with pytest.raises(error):
            usar(valor)


@pytest.mark.parametrize(("prefijo", "usar", "error"), CASOS)
def test_el_texto_numerico_se_acepta_con_espacios(prefijo, usar, error):
    minimo, maximo, _ = LIMITES[prefijo]
    usar(f" {minimo} ")
    usar(f"{maximo}\n")


@pytest.mark.parametrize(("prefijo", "usar", "error"), CASOS)
@pytest.mark.parametrize("valor", NO_NUMEROS, ids=repr)
def test_lo_que_no_es_numero_es_tipo_de_dato_invalido(
    prefijo, usar, error, valor
):
    with pytest.raises(TipoDeDatoInvalido):
        usar(valor)


@pytest.mark.parametrize(("prefijo", "usar", "error"), CASOS_SOLO_ENTEROS)
def test_los_enteros_no_aceptan_decimales_dentro_del_rango(
    prefijo, usar, error
):
    minimo, maximo, _ = LIMITES[prefijo]
    for valor in (minimo + 0.5, maximo - 0.5, f"{minimo}.5", f"{minimo},5"):
        with pytest.raises(TipoDeDatoInvalido):
            usar(valor)


@pytest.mark.parametrize(("prefijo", "usar", "error"), CASOS_SOLO_ENTEROS)
def test_un_decimal_sin_parte_fraccionaria_es_un_entero(prefijo, usar, error):
    minimo, maximo, _ = LIMITES[prefijo]
    usar(float(minimo))
    usar(f"{maximo}.0")


@pytest.mark.parametrize(
    ("prefijo", "usar", "error"), CASOS_CON_DECIMALES_PERMITIDOS
)
def test_los_porcentajes_y_temperaturas_aceptan_decimales(
    prefijo, usar, error
):
    minimo, maximo, _ = LIMITES[prefijo]
    usar(minimo + 0.5)
    usar(maximo - 0.5)
    usar(f"{minimo + 0.5}".replace(".", ","))


@pytest.mark.parametrize(
    "validar",
    [
        validar_humedad,
        validar_temperatura,
        validar_cantidad_agua_ml,
        validar_frecuencia_riego_dias,
        validar_region,
        validar_estado_id,
    ],
)
def test_none_no_es_un_numero_valido(validar):
    with pytest.raises(TipoDeDatoInvalido):
        validar(None)


def test_los_enteros_validados_devuelven_int_y_los_porcentajes_float():
    assert type(validar_region("2")) is int
    assert type(validar_frecuencia_riego_dias(7.0)) is int
    assert type(validar_cantidad_agua_ml("250")) is int
    assert type(validar_humedad(50)) is float
    assert type(validar_temperatura("21,5")) is float


# --- rangos de la especie: se cambian de a pares ---------------------------

RANGOS = [
    pytest.param(
        "cambiar_rango_humedad",
        "humedad_ideal_min",
        "humedad_ideal_max",
        catalogos.HUMEDAD_MIN,
        catalogos.HUMEDAD_MAX,
        id="humedad",
    ),
    pytest.param(
        "cambiar_rango_temperatura",
        "temp_min",
        "temp_max",
        catalogos.TEMPERATURA_MIN,
        catalogos.TEMPERATURA_MAX,
        id="temperatura",
    ),
]


@pytest.mark.parametrize(
    ("metodo", "campo_min", "campo_max", "bajo", "alto"), RANGOS
)
def test_el_rango_completo_y_el_mas_angosto_se_aceptan(
    metodo, campo_min, campo_max, bajo, alto
):
    especie = hacer_especie()
    getattr(especie, metodo)(bajo, alto)
    assert (getattr(especie, campo_min), getattr(especie, campo_max)) == (
        bajo,
        alto,
    )
    getattr(especie, metodo)(bajo, bajo + 0.001)
    assert getattr(especie, campo_max) == bajo + 0.001


@pytest.mark.parametrize(
    ("metodo", "campo_min", "campo_max", "bajo", "alto"), RANGOS
)
def test_un_rango_invertido_o_sin_ancho_se_rechaza(
    metodo, campo_min, campo_max, bajo, alto
):
    especie = hacer_especie()
    medio = (bajo + alto) / 2
    for minimo, maximo in ((medio, medio), (alto, bajo), (medio + 1, medio)):
        with pytest.raises(ValorFueraDeRango):
            getattr(especie, metodo)(minimo, maximo)


@pytest.mark.parametrize(
    ("metodo", "campo_min", "campo_max", "bajo", "alto"), RANGOS
)
def test_un_extremo_fuera_de_los_limites_se_rechaza(
    metodo, campo_min, campo_max, bajo, alto
):
    especie = hacer_especie()
    medio = (bajo + alto) / 2
    for minimo, maximo in ((bajo - 0.001, medio), (medio, alto + 0.001)):
        with pytest.raises(ValorFueraDeRango):
            getattr(especie, metodo)(minimo, maximo)


@pytest.mark.parametrize(
    ("metodo", "campo_min", "campo_max", "bajo", "alto"), RANGOS
)
def test_un_rango_rechazado_deja_el_anterior_intacto(
    metodo, campo_min, campo_max, bajo, alto
):
    especie = hacer_especie()
    antes = (getattr(especie, campo_min), getattr(especie, campo_max))
    with pytest.raises(ValorFueraDeRango):
        getattr(especie, metodo)(alto, bajo)
    with pytest.raises(TipoDeDatoInvalido):
        getattr(especie, metodo)("abc", alto)
    assert (getattr(especie, campo_min), getattr(especie, campo_max)) == antes


def test_el_constructor_de_la_especie_aplica_los_mismos_rangos():
    for cambios in (
        {"humedad_ideal_min": 70, "humedad_ideal_max": 40},
        {"humedad_ideal_min": -0.1},
        {"humedad_ideal_max": 100.1},
        {"temp_min": -20.1},
        {"temp_max": 60.1},
        {"temp_min": 30, "temp_max": 30},
    ):
        with pytest.raises(ValorFueraDeRango):
            hacer_especie(**cambios)
    hacer_especie(
        humedad_ideal_min=0,
        humedad_ideal_max=100,
        temp_min=-20,
        temp_max=60,
    )


def test_humedad_en_rango_incluye_los_bordes_de_la_especie():
    especie = hacer_especie(humedad_ideal_min=40, humedad_ideal_max=70)
    assert especie.humedad_en_rango(40)
    assert especie.humedad_en_rango(70)
    assert not especie.humedad_en_rango(39.999)
    assert not especie.humedad_en_rango(70.001)
    with pytest.raises(ValorFueraDeRango):
        especie.humedad_en_rango(100.1)
