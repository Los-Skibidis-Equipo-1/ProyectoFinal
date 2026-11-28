"""Pruebas de los tokens JWT de sesión."""

import base64
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
import pytest

from plantas.dominio.excepciones import (
    ConfiguracionInvalida,
    CredencialesInvalidas,
    ErrorDeAutenticacion,
    ErrorDeNegocio,
    FechaInvalida,
    TokenExpirado,
    TokenInvalido,
)
from plantas.seguridad.tokens import (
    ALGORITMO,
    CLAVE_LARGO_MINIMO,
    DURACION_DEFECTO,
    EMISOR,
    TOKEN_LARGO_MAXIMO,
    ServicioDeTokens,
)
from tests.fabricas import USUARIO_ID, hacer_usuario

# Llaves de mentira solo para las pruebas.
CLAVE = "k" * 40
OTRA_CLAVE = "o" * 40


def servicio(**opciones):
    return ServicioDeTokens(CLAVE, **opciones)


def ahora():
    return datetime.now(UTC)


def firmar(datos, clave=CLAVE, algoritmo="HS256"):
    """Crea un token con los datos exactos que se le den."""
    return jwt.encode(datos, clave, algorithm=algoritmo)


def datos_validos(**cambios):
    momento = int(ahora().timestamp())
    datos = {
        "iss": EMISOR,
        "sub": str(USUARIO_ID),
        "iat": momento,
        "exp": momento + 600,
        "jti": str(uuid4()),
        "reg": 2,
        "rol": "usuario",
    }
    datos.update(cambios)
    return {k: v for k, v in datos.items() if v is not None}


def sin_firma(token):
    return jwt.decode(token, options={"verify_signature": False})


def _b64(datos):
    crudo = json.dumps(datos, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(crudo).decode().rstrip("=")


# --- la llave --------------------------------------------------------------


def test_una_llave_de_32_caracteres_se_acepta_y_una_de_31_no():
    assert ServicioDeTokens("k" * CLAVE_LARGO_MINIMO)
    with pytest.raises(ConfiguracionInvalida):
        ServicioDeTokens("k" * (CLAVE_LARGO_MINIMO - 1))


@pytest.mark.parametrize("clave", [None, "", 123, b"k" * 40, ["k" * 40]])
def test_una_llave_que_falta_o_no_es_texto_se_rechaza(clave):
    with pytest.raises(ConfiguracionInvalida):
        ServicioDeTokens(clave)


def test_el_valor_de_ejemplo_de_env_example_no_se_acepta():
    ejemplo = "cambiar_por_un_valor_largo_y_aleatorio"
    assert len(ejemplo) >= CLAVE_LARGO_MINIMO
    with pytest.raises(ConfiguracionInvalida):
        ServicioDeTokens(ejemplo)


def test_el_error_de_configuracion_dice_la_variable_y_no_el_valor():
    with pytest.raises(ConfiguracionInvalida) as error:
        ServicioDeTokens("corta")
    assert error.value.variable == "JWT_SECRET"
    assert "JWT_SECRET" in str(error.value)
    assert "corta" not in str(error.value)


def test_la_llave_se_toma_de_la_variable_de_entorno():
    servicio_de_entorno = ServicioDeTokens.desde_entorno({"JWT_SECRET": CLAVE})
    token = servicio_de_entorno.emitir(hacer_usuario())
    assert servicio().verificar(token).usuario_id == USUARIO_ID


@pytest.mark.parametrize(
    "entorno",
    [{}, {"JWT_SECRET": ""}, {"JWT_SECRET": "corta"}, {"OTRA": CLAVE}],
)
def test_sin_la_variable_o_con_una_llave_debil_no_arranca(entorno):
    with pytest.raises(ConfiguracionInvalida):
        ServicioDeTokens.desde_entorno(entorno)


@pytest.mark.parametrize(
    "duracion",
    [timedelta(0), timedelta(seconds=-1), 30, "30 minutos"],
    ids=repr,
)
def test_una_duracion_que_no_es_positiva_se_rechaza(duracion):
    with pytest.raises(ConfiguracionInvalida):
        servicio(duracion=duracion)


def test_el_repr_no_muestra_la_llave():
    texto = repr(servicio()) + str(servicio())
    assert CLAVE not in texto
    assert "HS256" in texto


# --- emitir y verificar ----------------------------------------------------


def test_un_token_emitido_se_verifica_y_trae_los_datos_del_usuario():
    usuario = hacer_usuario(region_id=3, rol="admin")
    datos = servicio().verificar(servicio().emitir(usuario))
    assert datos.usuario_id == usuario.usuario_id
    assert datos.region_id == 3
    assert datos.rol == "admin"
    assert datos.es_admin is True
    assert isinstance(datos.token_id, UUID)


def test_por_defecto_el_token_dura_siete_dias():
    assert DURACION_DEFECTO == timedelta(days=7)
    datos = servicio().verificar(servicio().emitir(hacer_usuario()))
    assert datos.expira - datos.emitido == timedelta(days=7)
    assert servicio().duracion == timedelta(days=7)


def test_un_token_de_hace_seis_dias_todavia_vale_y_uno_de_hace_ocho_no():
    emisor = servicio()
    seis = emisor.emitir(hacer_usuario(), ahora=ahora() - timedelta(days=6))
    assert emisor.verificar(seis).usuario_id == USUARIO_ID
    ocho = emisor.emitir(hacer_usuario(), ahora=ahora() - timedelta(days=8))
    with pytest.raises(TokenExpirado):
        emisor.verificar(ocho)


def test_el_token_dura_lo_que_dice_el_servicio():
    datos = servicio().verificar(servicio().emitir(hacer_usuario()))
    assert datos.expira - datos.emitido == DURACION_DEFECTO
    corto = servicio(duracion=timedelta(minutes=5))
    datos = corto.verificar(corto.emitir(hacer_usuario()))
    assert datos.expira - datos.emitido == timedelta(minutes=5)


def test_el_token_usa_hs256_y_solo_lleva_datos_publicos():
    token = servicio().emitir(hacer_usuario())
    assert jwt.get_unverified_header(token)["alg"] == ALGORITMO == "HS256"
    contenido = sin_firma(token)
    assert set(contenido) == {"iss", "sub", "iat", "exp", "jti", "reg", "rol"}
    assert contenido["iss"] == EMISOR
    texto = json.dumps(contenido)
    for dato_personal in ("ana@example.com", "López", "Ana", "h" * 64):
        assert dato_personal not in texto


def test_cada_token_tiene_un_identificador_distinto():
    emisor = servicio()
    usuario = hacer_usuario()
    ids = {emisor.verificar(emisor.emitir(usuario)).token_id for _ in range(5)}
    assert len(ids) == 5


def test_un_usuario_normal_no_es_admin():
    datos = servicio().verificar(servicio().emitir(hacer_usuario()))
    assert datos.es_admin is False


def test_una_cuenta_desactivada_no_recibe_token():
    usuario = hacer_usuario(activo=False)
    with pytest.raises(CredencialesInvalidas):
        servicio().emitir(usuario)


def test_emitir_con_una_hora_sin_zona_horaria_se_rechaza():
    with pytest.raises(FechaInvalida):
        servicio().emitir(hacer_usuario(), ahora=datetime(2026, 11, 27, 12, 0))


def test_los_datos_del_token_no_se_pueden_modificar():
    datos = servicio().verificar(servicio().emitir(hacer_usuario()))
    with pytest.raises(AttributeError):
        datos.rol = "admin"


# --- expiración ------------------------------------------------------------


def test_un_token_vencido_se_rechaza():
    viejo = servicio().emitir(
        hacer_usuario(),
        ahora=ahora() - DURACION_DEFECTO - timedelta(seconds=5),
    )
    with pytest.raises(TokenExpirado):
        servicio().verificar(viejo)


def test_un_token_muy_antiguo_se_rechaza():
    viejo = servicio().emitir(
        hacer_usuario(), ahora=ahora() - timedelta(days=400)
    )
    with pytest.raises(TokenExpirado):
        servicio().verificar(viejo)


def test_un_token_a_pocos_segundos_de_vencer_todavia_vale():
    casi = servicio().emitir(
        hacer_usuario(),
        ahora=ahora() - DURACION_DEFECTO + timedelta(seconds=10),
    )
    assert servicio().verificar(casi).usuario_id == USUARIO_ID


def test_el_token_vence_segun_la_duracion_del_servicio_que_lo_emitio():
    corto = servicio(duracion=timedelta(seconds=30))
    token = corto.emitir(
        hacer_usuario(), ahora=ahora() - timedelta(seconds=40)
    )
    with pytest.raises(TokenExpirado):
        corto.verificar(token)


def test_un_token_vencido_tambien_es_un_token_invalido_y_un_error_de_negocio():
    viejo = servicio().emitir(
        hacer_usuario(),
        ahora=ahora() - DURACION_DEFECTO - timedelta(seconds=5),
    )
    with pytest.raises(TokenInvalido):
        servicio().verificar(viejo)
    with pytest.raises(ErrorDeAutenticacion):
        servicio().verificar(viejo)
    with pytest.raises(ErrorDeNegocio):
        servicio().verificar(viejo)


def test_un_token_emitido_en_el_futuro_se_rechaza():
    futuro = servicio().emitir(
        hacer_usuario(), ahora=ahora() + timedelta(hours=1)
    )
    with pytest.raises(TokenInvalido):
        servicio().verificar(futuro)


def test_un_token_sin_vencimiento_se_rechaza():
    with pytest.raises(TokenInvalido):
        servicio().verificar(firmar(datos_validos(exp=None)))


def test_un_vencimiento_que_no_es_numero_se_rechaza():
    for exp in ("mañana", [1], {"a": 1}):
        with pytest.raises(TokenInvalido):
            servicio().verificar(firmar(datos_validos(exp=exp)))


# --- firma y algoritmo -----------------------------------------------------


def test_un_token_firmado_con_otra_llave_se_rechaza():
    ajeno = ServicioDeTokens(OTRA_CLAVE).emitir(hacer_usuario())
    with pytest.raises(TokenInvalido):
        servicio().verificar(ajeno)


def test_un_token_con_el_contenido_alterado_se_rechaza():
    token = servicio().emitir(hacer_usuario(rol="usuario"))
    encabezado, _, firma = token.split(".")
    alterado = {**sin_firma(token), "rol": "admin"}
    falso = f"{encabezado}.{_b64(alterado)}.{firma}"
    with pytest.raises(TokenInvalido):
        servicio().verificar(falso)


def test_un_token_con_la_firma_alterada_se_rechaza():
    encabezado, contenido, firma = (
        servicio().emitir(hacer_usuario()).split(".")
    )
    cambio = "A" if firma[0] != "A" else "B"
    with pytest.raises(TokenInvalido):
        servicio().verificar(f"{encabezado}.{contenido}.{cambio}{firma[1:]}")


def test_un_token_sin_firma_se_rechaza():
    encabezado, contenido, _ = servicio().emitir(hacer_usuario()).split(".")
    for falso in (f"{encabezado}.{contenido}.", f"{encabezado}.{contenido}"):
        with pytest.raises(TokenInvalido):
            servicio().verificar(falso)


def test_el_algoritmo_none_se_rechaza():
    encabezado = _b64({"alg": "none", "typ": "JWT"})
    falso = f"{encabezado}.{_b64(datos_validos())}."
    with pytest.raises(TokenInvalido):
        servicio().verificar(falso)


LLAVE_LARGA = "L" * 80  # el largo recomendado para HS512; evita advertencias


@pytest.mark.parametrize("algoritmo", ["HS384", "HS512"])
def test_otro_algoritmo_con_la_misma_llave_se_rechaza(algoritmo):
    token = firmar(datos_validos(), clave=LLAVE_LARGA, algoritmo=algoritmo)
    with pytest.raises(TokenInvalido):
        ServicioDeTokens(LLAVE_LARGA).verificar(token)


def test_el_algoritmo_lo_decide_el_servidor_y_no_el_token():
    token = firmar(datos_validos(), clave=LLAVE_LARGA, algoritmo="HS512")
    assert jwt.get_unverified_header(token)["alg"] == "HS512"
    with pytest.raises(TokenInvalido):
        ServicioDeTokens(LLAVE_LARGA).verificar(token)


# --- datos que faltan o están mal ------------------------------------------


@pytest.mark.parametrize(
    "dato", ["exp", "iat", "iss", "sub", "jti", "reg", "rol"]
)
def test_un_token_al_que_le_falta_un_dato_se_rechaza(dato):
    with pytest.raises(TokenInvalido):
        servicio().verificar(firmar(datos_validos(**{dato: None})))


@pytest.mark.parametrize(
    ("dato", "valor"),
    [
        ("iss", "otra-api"),
        ("iss", ""),
        ("sub", "no-es-uuid"),
        ("sub", ""),
        ("sub", 123),
        ("sub", "null"),
        ("jti", "no-es-uuid"),
        ("jti", 5),
        ("reg", 0),
        ("reg", 4),
        ("reg", -1),
        ("reg", "2"),
        ("reg", 2.5),
        ("reg", True),
        ("reg", [2]),
        ("rol", "root"),
        ("rol", "ADMIN"),
        ("rol", " admin"),
        ("rol", ""),
        ("rol", ["admin"]),
        ("rol", 1),
    ],
    ids=repr,
)
def test_un_dato_con_valor_invalido_se_rechaza(dato, valor):
    with pytest.raises(TokenInvalido):
        servicio().verificar(firmar(datos_validos(**{dato: valor})))


@pytest.mark.parametrize("region", [1, 2, 3])
@pytest.mark.parametrize("rol", ["usuario", "admin"])
def test_todas_las_regiones_y_roles_validos_se_aceptan(region, rol):
    datos = servicio().verificar(firmar(datos_validos(reg=region, rol=rol)))
    assert (datos.region_id, datos.rol) == (region, rol)


# --- lo que no es un token -------------------------------------------------


@pytest.mark.parametrize(
    "token",
    [
        None,
        "",
        " ",
        "abc",
        "a.b.c",
        "..",
        "a.b.c.d",
        123,
        b"bytes",
        ["x"],
        {"a": 1},
        "x" * (TOKEN_LARGO_MAXIMO + 1),
        "Bearer " + "a.b.c",
        "eyJhbGciOiJIUzI1NiJ9.e30.",
    ],
    ids=repr,
)
def test_lo_que_no_es_un_token_se_rechaza(token):
    with pytest.raises(TokenInvalido):
        servicio().verificar(token)


def test_un_token_con_espacios_o_saltos_alrededor_se_rechaza():
    token = servicio().emitir(hacer_usuario())
    for sucio in (f" {token}", f"{token} ", f"{token}\n"):
        with pytest.raises(TokenInvalido):
            servicio().verificar(sucio)


def test_los_errores_son_genericos_y_no_repiten_el_token():
    token = servicio().emitir(hacer_usuario())
    alterado = token[:-3] + ("AAA" if not token.endswith("AAA") else "BBB")
    with pytest.raises(TokenInvalido) as error:
        servicio().verificar(alterado)
    assert str(error.value) == "El token no es válido"
    assert alterado not in str(error.value) + repr(error.value)
    assert error.value.__cause__ is None
    assert error.value.__suppress_context__ is True


def test_el_error_de_credenciales_no_dice_cual_dato_fallo():
    with pytest.raises(CredencialesInvalidas) as error:
        servicio().emitir(hacer_usuario(activo=False))
    assert str(error.value) == "Correo o contraseña incorrectos"
    assert "ana@example.com" not in str(error.value)


def test_un_token_expirado_dice_que_vencio_sin_mas_detalles():
    viejo = servicio().emitir(
        hacer_usuario(),
        ahora=ahora() - DURACION_DEFECTO - timedelta(seconds=5),
    )
    with pytest.raises(TokenExpirado) as error:
        servicio().verificar(viejo)
    assert str(error.value) == "El token ya venció"
    assert viejo not in str(error.value)
