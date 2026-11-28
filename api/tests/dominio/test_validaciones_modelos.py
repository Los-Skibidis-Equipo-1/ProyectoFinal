"""Pruebas de las validaciones que usan las clases del dominio (B3)."""

from datetime import UTC, date, datetime, timedelta

import pytest

from plantas.dominio.excepciones import (
    CampoVacio,
    ErrorDeValidacion,
    FechaInvalida,
    FormatoInvalido,
    TipoDeDatoInvalido,
    ValorFueraDeRango,
)
from plantas.dominio.validaciones import (
    validar_booleano,
    validar_correo,
    validar_entero_positivo,
    validar_estado_id,
    validar_fecha_calendario_no_futura,
    validar_par_ordenado,
    validar_password_hash,
    validar_texto_opcional,
)

HOY = date(2026, 11, 27)


@pytest.mark.parametrize("valor", [True, False])
def test_booleano_acepta_solo_booleanos(valor):
    assert validar_booleano(valor, "activo") is valor


@pytest.mark.parametrize("valor", [0, 1, "True", None, "si"])
def test_booleano_rechaza_lo_demas(valor):
    with pytest.raises(TipoDeDatoInvalido, match="activo"):
        validar_booleano(valor, "activo")


@pytest.mark.parametrize(("valor", "esperado"), [(1, 1), ("7", 7), (3.0, 3)])
def test_entero_positivo_valido(valor, esperado):
    resultado = validar_entero_positivo(valor, "id")
    assert resultado == esperado
    assert isinstance(resultado, int)


@pytest.mark.parametrize("valor", [0, -1, 2.5])
def test_entero_positivo_invalido(valor):
    with pytest.raises(ValorFueraDeRango, match="id"):
        validar_entero_positivo(valor, "id")


@pytest.mark.parametrize(("valor", "esperado"), [(1, 1), ("32", 32), (15, 15)])
def test_estado_valido(valor, esperado):
    assert validar_estado_id(valor) == esperado


@pytest.mark.parametrize("valor", [0, 33, -1])
def test_estado_fuera_de_rango(valor):
    with pytest.raises(ValorFueraDeRango):
        validar_estado_id(valor)


def test_estado_debe_ser_entero():
    with pytest.raises(TipoDeDatoInvalido, match="entero"):
        validar_estado_id(2.5)


@pytest.mark.parametrize("valor", [None, "", "   "])
def test_texto_opcional_vacio_es_none(valor):
    assert validar_texto_opcional(valor, "notas", 10) is None


def test_texto_opcional_con_contenido():
    assert validar_texto_opcional("  hola ", "notas", 10) == "hola"


def test_texto_opcional_demasiado_largo():
    with pytest.raises(ValorFueraDeRango):
        validar_texto_opcional("x" * 11, "notas", 10)


def test_texto_opcional_que_no_es_texto():
    with pytest.raises(TipoDeDatoInvalido):
        validar_texto_opcional(5, "notas", 10)


def test_par_ordenado_valido():
    assert validar_par_ordenado(10, "80,5", "humedad", 0, 100) == (10.0, 80.5)


@pytest.mark.parametrize(
    ("minimo", "maximo"), [(50, 50), (60, 40), (-1, 50), (10, 101)]
)
def test_par_ordenado_invalido(minimo, maximo):
    with pytest.raises(ValorFueraDeRango):
        validar_par_ordenado(minimo, maximo, "humedad", 0, 100)


def test_par_desordenado_dice_minimo_y_maximo():
    with pytest.raises(ValorFueraDeRango, match="menor que el máximo"):
        validar_par_ordenado(60, 40, "humedad", 0, 100)


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("ana@correo.com", "ana@correo.com"),
        ("  Ana.Lopez@Correo.COM ", "ana.lopez@correo.com"),
        ("a+b@sub.dominio.mx", "a+b@sub.dominio.mx"),
    ],
)
def test_correo_valido_se_normaliza(entrada, esperado):
    assert validar_correo(entrada) == esperado


@pytest.mark.parametrize(
    "entrada",
    [
        "sin-arroba",
        "a@b",
        "a b@c.com",
        "@x.com",
        "a@@b.com",
        "a@b.",
        "a@.com",
    ],
)
def test_correo_con_formato_invalido(entrada):
    with pytest.raises(FormatoInvalido):
        validar_correo(entrada)


def test_correo_demasiado_largo():
    with pytest.raises(FormatoInvalido):
        validar_correo("x" * 250 + "@a.com")


def test_correo_vacio_o_que_no_es_texto():
    with pytest.raises(CampoVacio):
        validar_correo("  ")
    with pytest.raises(TipoDeDatoInvalido):
        validar_correo(None)


def test_el_error_de_correo_no_repite_el_correo():
    with pytest.raises(FormatoInvalido) as info:
        validar_correo("ana-sin-arroba")
    assert "ana-sin-arroba" not in str(info.value)
    assert info.value.valor is None


def test_password_hash_valido():
    hash_largo = "scrypt$" + "a" * 40
    assert validar_password_hash(hash_largo) == hash_largo


@pytest.mark.parametrize("valor", ["corto", "", None, 123, "x" * 31])
def test_password_hash_invalido(valor):
    with pytest.raises(FormatoInvalido):
        validar_password_hash(valor)


def test_el_error_de_hash_no_guarda_el_valor():
    with pytest.raises(FormatoInvalido) as info:
        validar_password_hash("secreto123")
    assert "secreto123" not in str(info.value)
    assert info.value.valor is None


def test_fecha_de_calendario_valida():
    assert validar_fecha_calendario_no_futura(HOY, "fecha", HOY) == HOY
    assert validar_fecha_calendario_no_futura(
        HOY - timedelta(days=30), "fecha", HOY
    ) == date(2026, 10, 28)


def test_fecha_de_calendario_futura():
    with pytest.raises(FechaInvalida, match="futuro"):
        validar_fecha_calendario_no_futura(HOY + timedelta(days=1), "f", HOY)


@pytest.mark.parametrize("valor", [None, "2026-01-01", datetime(2026, 1, 1)])
def test_fecha_de_calendario_que_no_es_fecha(valor):
    with pytest.raises(FechaInvalida, match="fecha"):
        validar_fecha_calendario_no_futura(valor, "fecha", HOY)


def test_fecha_de_calendario_sin_pasar_hoy_usa_el_reloj():
    assert validar_fecha_calendario_no_futura(date(2020, 1, 1), "fecha")
    manana = datetime.now(UTC).date() + timedelta(days=2)
    with pytest.raises(FechaInvalida):
        validar_fecha_calendario_no_futura(manana, "fecha")


def test_todos_los_errores_son_de_validacion():
    with pytest.raises(ErrorDeValidacion):
        validar_booleano(1, "x")
