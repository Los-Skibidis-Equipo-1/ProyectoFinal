"""Pruebas de las validaciones del dominio."""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from plantas.dominio import validaciones
from plantas.dominio.excepciones import (
    CampoVacio,
    FechaInvalida,
    OpcionNoPermitida,
    TipoDeDatoInvalido,
    ValorFueraDeRango,
)
from plantas.dominio.validaciones import (
    ResultadoLecturas,
    convertir_a_numero,
    procesar_lecturas_humedad,
    validar_cantidad_agua_ml,
    validar_fecha_no_futura,
    validar_frecuencia_riego_dias,
    validar_humedad,
    validar_opcion,
    validar_rango,
    validar_temperatura,
    validar_texto_no_vacio,
)

# ---------------------------------------------------------------- números


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [(5, 5.0), (45.5, 45.5), ("45", 45.0), ("45.5", 45.5), (" 45,5 ", 45.5)],
)
def test_convertir_a_numero_acepta_numeros_y_textos_numericos(
    entrada, esperado
):
    assert convertir_a_numero(entrada, "humedad") == esperado


@pytest.mark.parametrize(
    "entrada",
    ["abc", "", "   ", None, True, False, [1], "nan", "inf", float("nan")],
)
def test_convertir_a_numero_rechaza_lo_que_no_es_numero(entrada):
    with pytest.raises(TipoDeDatoInvalido):
        convertir_a_numero(entrada, "humedad")


def test_convertir_a_numero_conserva_el_error_original():
    with pytest.raises(TipoDeDatoInvalido) as info:
        convertir_a_numero("abc", "humedad")
    assert isinstance(info.value.__cause__, ValueError)
    assert info.value.campo == "humedad"
    assert info.value.valor == "abc"


def test_el_mensaje_de_error_dice_el_campo():
    with pytest.raises(TipoDeDatoInvalido, match="humedad"):
        convertir_a_numero("abc", "humedad")


# ----------------------------------------------------------------- rangos


@pytest.mark.parametrize("valor", [0, 0.0, 50, 100, "100", "99,9"])
def test_humedad_valida_incluye_los_extremos(valor):
    assert 0 <= validar_humedad(valor) <= 100


@pytest.mark.parametrize("valor", [-0.1, 100.1, -1, 101, "150"])
def test_humedad_fuera_de_rango(valor):
    with pytest.raises(ValorFueraDeRango):
        validar_humedad(valor)


def test_humedad_con_texto_es_error_de_tipo_no_de_rango():
    with pytest.raises(TipoDeDatoInvalido):
        validar_humedad("mucha")


@pytest.mark.parametrize("valor", [-20, 0, 25.5, 60])
def test_temperatura_valida(valor):
    assert validar_temperatura(valor) == float(valor)


@pytest.mark.parametrize("valor", [-20.1, 60.1, 100])
def test_temperatura_fuera_de_rango(valor):
    with pytest.raises(ValorFueraDeRango):
        validar_temperatura(valor)


def test_validar_rango_con_limites_propios():
    assert validar_rango(5, "edad", 1, 10) == 5.0
    with pytest.raises(ValorFueraDeRango, match="entre 1 y 10"):
        validar_rango(11, "edad", 1, 10)


@pytest.mark.parametrize("valor", [0.1, 1, 250, "300,5"])
def test_cantidad_de_agua_valida(valor):
    assert validar_cantidad_agua_ml(valor) > 0


@pytest.mark.parametrize("valor", [0, -1, -0.5, "0"])
def test_cantidad_de_agua_debe_ser_mayor_que_cero(valor):
    with pytest.raises(ValorFueraDeRango, match="mayor que 0"):
        validar_cantidad_agua_ml(valor)


@pytest.mark.parametrize(
    ("valor", "esperado"), [(1, 1), (7, 7), ("30", 30), (365, 365)]
)
def test_frecuencia_de_riego_valida(valor, esperado):
    resultado = validar_frecuencia_riego_dias(valor)
    assert resultado == esperado
    assert isinstance(resultado, int)


@pytest.mark.parametrize("valor", [0, 366, -3])
def test_frecuencia_de_riego_fuera_de_rango(valor):
    with pytest.raises(ValorFueraDeRango):
        validar_frecuencia_riego_dias(valor)


def test_frecuencia_de_riego_debe_ser_entera():
    with pytest.raises(TipoDeDatoInvalido, match="entero"):
        validar_frecuencia_riego_dias(2.5)


# ------------------------------------------------------------------ texto


def test_texto_se_devuelve_sin_espacios_en_los_extremos():
    assert validar_texto_no_vacio("  Monstera  ", "apodo") == "Monstera"


@pytest.mark.parametrize("valor", ["", "   ", "\t\n"])
def test_texto_vacio_o_solo_espacios(valor):
    with pytest.raises(CampoVacio, match="apodo"):
        validar_texto_no_vacio(valor, "apodo")


@pytest.mark.parametrize("valor", [None, 5, ["a"]])
def test_texto_que_no_es_texto(valor):
    with pytest.raises(TipoDeDatoInvalido):
        validar_texto_no_vacio(valor, "apodo")


def test_texto_con_largo_maximo():
    assert validar_texto_no_vacio("abc", "apodo", largo_maximo=3) == "abc"
    with pytest.raises(ValorFueraDeRango, match="más de 3"):
        validar_texto_no_vacio("abcd", "apodo", largo_maximo=3)


# --------------------------------------------------------------- opciones


def test_opcion_valida_se_normaliza():
    opciones = ("casa", "oficina")
    assert validar_opcion(" Casa ", "tipo de espacio", opciones) == "casa"


def test_opcion_no_permitida_lista_las_validas():
    with pytest.raises(OpcionNoPermitida, match="casa, oficina"):
        validar_opcion("jardín", "tipo de espacio", ("casa", "oficina"))


def test_opcion_vacia_es_campo_vacio():
    with pytest.raises(CampoVacio):
        validar_opcion("  ", "tipo de espacio", ("casa",))


def test_opcion_acepta_cualquier_iterable_una_sola_vez():
    generador = (x for x in ("casa", "patio"))
    assert validar_opcion("patio", "tipo de espacio", generador) == "patio"


# ----------------------------------------------------------------- fechas

AHORA = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)


def test_fecha_pasada_es_valida():
    ayer = AHORA - timedelta(days=1)
    assert validar_fecha_no_futura(ayer, "fecha", AHORA) == ayer


def test_fecha_igual_a_ahora_es_valida():
    assert validar_fecha_no_futura(AHORA, "fecha", AHORA) == AHORA


def test_fecha_futura_se_rechaza():
    manana = AHORA + timedelta(seconds=1)
    with pytest.raises(FechaInvalida, match="futuro"):
        validar_fecha_no_futura(manana, "fecha", AHORA)


def test_fecha_sin_zona_horaria_se_rechaza():
    with pytest.raises(FechaInvalida, match="zona horaria"):
        validar_fecha_no_futura(datetime(2026, 1, 1), "fecha", AHORA)


@pytest.mark.parametrize("valor", [None, "2026-01-01", 20260101])
def test_fecha_que_no_es_fecha(valor):
    with pytest.raises(FechaInvalida, match="vacía"):
        validar_fecha_no_futura(valor, "fecha", AHORA)


def test_fecha_compara_bien_entre_zonas_horarias():
    mexico = timezone(timedelta(hours=-6))
    # 07:00 en México son las 13:00 UTC: es posterior a AHORA (12:00 UTC)
    with pytest.raises(FechaInvalida):
        validar_fecha_no_futura(
            datetime(2026, 11, 27, 7, 0, tzinfo=mexico), "fecha", AHORA
        )
    # 05:00 en México son las 11:00 UTC: es anterior
    valor = datetime(2026, 11, 27, 5, 0, tzinfo=mexico)
    assert validar_fecha_no_futura(valor, "fecha", AHORA) == valor


def test_fecha_sin_pasar_ahora_usa_el_reloj_real():
    assert validar_fecha_no_futura(datetime(2020, 1, 1, tzinfo=UTC), "fecha")
    futuro = datetime.now(UTC) + timedelta(days=1)
    with pytest.raises(FechaInvalida):
        validar_fecha_no_futura(futuro, "fecha")


# ----------------------------------------- try / except / else / finally


def test_procesar_lecturas_separa_validas_y_errores():
    resultado = procesar_lecturas_humedad([40, "55,5", "abc", 120, None, 0])
    assert resultado.validas == [40.0, 55.5, 0.0]
    assert [posicion for posicion, _ in resultado.errores] == [3, 4, 5]
    assert "abc" in resultado.errores[0][1]
    assert "entre 0 y 100" in resultado.errores[1][1]


def test_procesar_lecturas_cuenta_todas_con_finally():
    resultado = procesar_lecturas_humedad([40, "abc", 120, 70])
    assert resultado.procesadas == 4
    assert len(resultado.validas) + len(resultado.errores) == 4


def test_una_lectura_mala_no_detiene_el_lote():
    resultado = procesar_lecturas_humedad(["mala", 50, 60])
    assert resultado.validas == [50.0, 60.0]


def test_procesar_lecturas_con_lote_vacio():
    resultado = procesar_lecturas_humedad([])
    assert resultado == ResultadoLecturas(validas=[], errores=[], procesadas=0)


def test_procesar_lecturas_acepta_un_generador():
    resultado = procesar_lecturas_humedad(x for x in (10, 20))
    assert resultado.validas == [10.0, 20.0]


def test_un_objeto_desconocido_se_registra_como_error_de_tipo():
    resultado = procesar_lecturas_humedad([object()])
    assert resultado.validas == []
    assert resultado.procesadas == 1
    assert "humedad debe ser un número" in resultado.errores[0][1]


def test_un_error_inesperado_no_se_esconde(monkeypatch):
    def falla(_valor):
        raise RuntimeError("falla inesperada")

    monkeypatch.setattr(validaciones, "validar_humedad", falla)
    with pytest.raises(RuntimeError, match="inesperada"):
        procesar_lecturas_humedad([50])
