"""Pruebas del hash de contraseñas con scrypt."""

import base64
import hashlib
from unittest import mock

import pytest

from plantas.dominio.excepciones import (
    CampoVacio,
    ErrorDeValidacion,
    FormatoInvalido,
    TipoDeDatoInvalido,
    ValorFueraDeRango,
)
from plantas.dominio.validaciones import validar_password_hash
from plantas.seguridad import contrasenas
from plantas.seguridad.contrasenas import (
    CONTRASENA_LARGO_MAXIMO,
    CONTRASENA_LARGO_MINIMO,
    N_DEFECTO,
    hashear_contrasena,
    necesita_rehash,
    validar_contrasena_nueva,
    verificar_contrasena,
)
from tests.fabricas import hacer_usuario

# Contraseña de mentira para las pruebas; costo bajo para que sean rápidas.
CLAVE = "contraseña de mentira 123"
RAPIDO = {"n": 2**4, "r": 8, "p": 1}


def hash_rapido(contrasena=CLAVE):
    return hashear_contrasena(contrasena, **RAPIDO)


def _b64_a_bytes(texto):
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


# --- el hash ---------------------------------------------------------------


def test_el_hash_tiene_el_formato_y_los_parametros_esperados():
    partes = hash_rapido().split("$")
    assert partes[0] == "scrypt"
    assert partes[1:4] == ["16", "8", "1"]
    assert len(_b64_a_bytes(partes[4])) == 16
    assert len(_b64_a_bytes(partes[5])) == 32


def test_con_los_parametros_por_defecto_usa_un_costo_alto():
    partes = hashear_contrasena(CLAVE).split("$")
    assert int(partes[1]) == N_DEFECTO == 2**15
    assert partes[2:4] == ["8", "1"]


def test_la_contrasena_no_aparece_en_el_hash():
    texto = hash_rapido()
    assert CLAVE not in texto
    assert CLAVE.replace(" ", "") not in texto


def test_el_hash_cumple_la_regla_de_la_base_y_del_usuario():
    texto = hash_rapido()
    assert len(texto) >= 32
    assert validar_password_hash(texto) == texto
    assert hacer_usuario(password_hash=texto).password_hash == texto


def test_la_misma_contrasena_da_hashes_distintos_por_la_sal():
    hashes = {hash_rapido() for _ in range(5)}
    assert len(hashes) == 5
    assert len({h.split("$")[4] for h in hashes}) == 5


def test_es_realmente_scrypt_con_la_sal_guardada():
    partes = hash_rapido().split("$")
    esperado = hashlib.scrypt(
        CLAVE.encode("utf-8"),
        salt=_b64_a_bytes(partes[4]),
        n=16,
        r=8,
        p=1,
        dklen=32,
    )
    assert _b64_a_bytes(partes[5]) == esperado


# --- verificar -------------------------------------------------------------


def test_la_contrasena_correcta_se_verifica():
    assert verificar_contrasena(CLAVE, hash_rapido()) is True


def test_con_los_parametros_por_defecto_tambien_se_verifica():
    texto = hashear_contrasena(CLAVE)
    assert verificar_contrasena(CLAVE, texto) is True
    assert verificar_contrasena(CLAVE + "x", texto) is False


@pytest.mark.parametrize(
    "intento",
    [
        CLAVE + " ",
        " " + CLAVE,
        CLAVE.upper(),
        CLAVE[:-1],
        CLAVE + "x",
        "otra contraseña distinta",
        "",
        " ",
    ],
    ids=repr,
)
def test_una_contrasena_incorrecta_no_se_verifica(intento):
    assert verificar_contrasena(intento, hash_rapido()) is False


@pytest.mark.parametrize("intento", [None, 123, b"bytes", ["x"], object()])
def test_lo_que_no_es_texto_no_se_verifica_y_no_lanza(intento):
    assert verificar_contrasena(intento, hash_rapido()) is False


def test_una_contrasena_enorme_se_descarta_sin_calcular_el_hash():
    texto = hash_rapido()
    with mock.patch.object(contrasenas, "_calcular") as calcular:
        assert verificar_contrasena("x" * 10_000, texto) is False
    calcular.assert_not_called()


def test_la_misma_frase_con_distinta_forma_unicode_es_la_misma_contrasena():
    compuesta = "contrase\u00f1a-\u00e9-1234"  # é como un solo carácter
    descompuesta = "contrase\u00f1a-e\u0301-1234"  # e + acento combinado
    assert compuesta != descompuesta
    assert verificar_contrasena(descompuesta, hash_rapido(compuesta))
    assert verificar_contrasena(compuesta, hash_rapido(descompuesta))


def test_un_hash_alterado_no_verifica():
    texto = hash_rapido()
    partes = texto.split("$")
    partes[5] = ("A" if partes[5][0] != "A" else "B") + partes[5][1:]
    assert verificar_contrasena(CLAVE, "$".join(partes)) is False


def test_dos_usuarios_con_la_misma_contrasena_no_se_pueden_cruzar():
    a, b = hash_rapido(), hash_rapido()
    assert a != b
    assert verificar_contrasena(CLAVE, a) and verificar_contrasena(CLAVE, b)
    partes_a, partes_b = a.split("$"), b.split("$")
    mezclado = "$".join(partes_a[:5] + [partes_b[5]])
    assert verificar_contrasena(CLAVE, mezclado) is False


def test_la_comparacion_es_en_tiempo_constante():
    with mock.patch.object(
        contrasenas.hmac,
        "compare_digest",
        wraps=contrasenas.hmac.compare_digest,
    ) as comparar:
        verificar_contrasena(CLAVE, hash_rapido())
        verificar_contrasena("incorrecta 123", hash_rapido())
    assert comparar.call_count == 2


# --- contraseñas nuevas ----------------------------------------------------


@pytest.mark.parametrize(
    "largo", [CONTRASENA_LARGO_MINIMO, 20, CONTRASENA_LARGO_MAXIMO]
)
def test_los_largos_permitidos_se_aceptan(largo):
    contrasena = "a" * largo
    assert validar_contrasena_nueva(contrasena) == contrasena
    assert hashear_contrasena(contrasena, **RAPIDO)


@pytest.mark.parametrize(
    "largo",
    [1, CONTRASENA_LARGO_MINIMO - 1, CONTRASENA_LARGO_MAXIMO + 1, 5000],
)
def test_los_largos_no_permitidos_se_rechazan(largo):
    with pytest.raises(ValorFueraDeRango):
        hashear_contrasena("a" * largo, **RAPIDO)


def test_cuenta_caracteres_y_no_bytes():
    assert validar_contrasena_nueva("ñ" * CONTRASENA_LARGO_MINIMO)
    assert validar_contrasena_nueva("ñ" * CONTRASENA_LARGO_MAXIMO)
    with pytest.raises(ValorFueraDeRango):
        validar_contrasena_nueva("ñ" * (CONTRASENA_LARGO_MAXIMO + 1))


@pytest.mark.parametrize("vacia", ["", " ", " " * 20, "\t\n  "], ids=repr)
def test_una_contrasena_vacia_o_de_espacios_se_rechaza(vacia):
    with pytest.raises(CampoVacio):
        validar_contrasena_nueva(vacia)


@pytest.mark.parametrize("valor", [None, 12345678, b"12345678", ["x"]])
def test_una_contrasena_que_no_es_texto_se_rechaza(valor):
    with pytest.raises(TipoDeDatoInvalido):
        hashear_contrasena(valor, **RAPIDO)


def test_los_espacios_de_los_extremos_forman_parte_de_la_contrasena():
    texto = hash_rapido("  con espacios  ")
    assert verificar_contrasena("  con espacios  ", texto)
    assert not verificar_contrasena("con espacios", texto)


@pytest.mark.parametrize("contrasena", ["corta", "a" * 500, "  ", 12345678])
def test_los_errores_nunca_llevan_la_contrasena(contrasena):
    with pytest.raises(ErrorDeValidacion) as error:
        validar_contrasena_nueva(contrasena)
    assert error.value.valor is None
    if isinstance(contrasena, str) and contrasena.strip():
        assert contrasena not in str(error.value)


def test_la_contrasena_de_un_error_no_sale_en_repr_ni_en_str():
    secreta = "corta"
    with pytest.raises(ValorFueraDeRango) as error:
        validar_contrasena_nueva(secreta)
    assert secreta not in str(error.value)
    assert secreta not in repr(error.value)
    assert secreta not in repr(error.value.__dict__)


# --- parámetros de costo ---------------------------------------------------


@pytest.mark.parametrize(
    "parametros",
    [
        {"n": 2**3},
        {"n": 2**21},
        {"n": 1000},
        {"n": 0},
        {"n": 16.0},
        {"r": 0},
        {"r": 33},
        {"p": 0},
        {"p": 17},
    ],
    ids=repr,
)
def test_los_parametros_fuera_de_lo_permitido_se_rechazan(parametros):
    base = {"n": 2**4, "r": 8, "p": 1} | parametros
    with pytest.raises(FormatoInvalido):
        hashear_contrasena(CLAVE, **base)


def test_un_hash_de_menor_costo_pide_recalcularse():
    assert necesita_rehash(hash_rapido()) is True
    assert necesita_rehash(hashear_contrasena(CLAVE)) is False
    mayor = hashear_contrasena(CLAVE, n=2**16)
    assert necesita_rehash(mayor) is False


# --- hash guardado dañado --------------------------------------------------


def _con_cambio(posicion, valor):
    partes = hash_rapido().split("$")
    partes[posicion] = valor
    return "$".join(partes)


HASHES_DANADOS = [
    None,
    123,
    "",
    "no es un hash",
    "scrypt",
    "scrypt$16$8$1$sal",
    hash_rapido() + "$extra",
    _con_cambio(0, "bcrypt"),
    _con_cambio(0, "SCRYPT"),
    _con_cambio(1, "abc"),
    _con_cambio(1, "-16"),
    _con_cambio(1, "17"),
    _con_cambio(1, str(2**40)),
    _con_cambio(2, "0"),
    _con_cambio(3, "100"),
    _con_cambio(4, "!!!!"),
    _con_cambio(4, "AAAA"),
    _con_cambio(5, "AAAA"),
    _con_cambio(5, ""),
]


@pytest.mark.parametrize("danado", HASHES_DANADOS, ids=repr)
def test_un_hash_guardado_danado_lanza_formato_invalido(danado):
    with pytest.raises(FormatoInvalido):
        verificar_contrasena(CLAVE, danado)
    with pytest.raises(FormatoInvalido):
        necesita_rehash(danado)


def test_un_hash_con_un_costo_exagerado_no_se_calcula():
    exagerado = _con_cambio(1, str(2**30))
    with mock.patch.object(contrasenas, "_calcular") as calcular:
        with pytest.raises(FormatoInvalido):
            verificar_contrasena(CLAVE, exagerado)
    calcular.assert_not_called()


def test_el_error_del_hash_danado_no_repite_el_hash_ni_la_contrasena():
    with pytest.raises(FormatoInvalido) as error:
        verificar_contrasena(CLAVE, "scrypt$basura")
    assert "basura" not in str(error.value)
    assert CLAVE not in str(error.value)
