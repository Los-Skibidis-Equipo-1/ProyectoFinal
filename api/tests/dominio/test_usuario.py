"""Pruebas de la clase Usuario."""

from uuid import UUID

import pytest

from plantas.dominio.excepciones import (
    CampoVacio,
    ErrorDeValidacion,
    FormatoInvalido,
    OpcionNoPermitida,
    TipoDeDatoInvalido,
    ValorFueraDeRango,
)
from plantas.dominio.usuario import Usuario

HASH = "scrypt$n=16384$" + "a" * 40
ID = "11111111-1111-1111-1111-111111111111"


def datos(**cambios):
    base = {
        "region_id": 2,
        "nombre": "Ana",
        "apellidos": "López Pérez",
        "correo": "Ana.Lopez@Correo.com",
        "password_hash": HASH,
        "estado_id": 1,
    }
    base.update(cambios)
    return base


@pytest.fixture
def usuario():
    return Usuario(**datos(usuario_id=ID))


def test_se_crea_con_datos_validos(usuario):
    assert usuario.region_id == 2
    assert usuario.nombre == "Ana"
    assert usuario.apellidos == "López Pérez"
    assert usuario.nombre_completo == "Ana López Pérez"
    assert usuario.estado_id == 1
    assert usuario.rol == "usuario"
    assert usuario.activo is True
    assert usuario.es_admin is False


def test_el_correo_se_guarda_normalizado(usuario):
    assert usuario.correo == "ana.lopez@correo.com"


def test_genera_un_uuid_si_no_se_da_id():
    uno = Usuario(**datos())
    otro = Usuario(**datos())
    assert isinstance(uno.usuario_id, UUID)
    assert uno.usuario_id != otro.usuario_id


def test_acepta_el_id_como_texto_o_uuid(usuario):
    assert usuario.usuario_id == UUID(ID)
    assert Usuario(**datos(usuario_id=UUID(ID))).usuario_id == UUID(ID)


def test_id_invalido():
    with pytest.raises(TipoDeDatoInvalido):
        Usuario(**datos(usuario_id="123"))


@pytest.mark.parametrize("region", [0, 4, -1])
def test_region_fuera_de_rango(region):
    with pytest.raises(ValorFueraDeRango):
        Usuario(**datos(region_id=region))


@pytest.mark.parametrize("campo", ["nombre", "apellidos"])
def test_nombre_y_apellidos_obligatorios(campo):
    with pytest.raises(CampoVacio):
        Usuario(**datos(**{campo: "  "}))


def test_largos_maximos():
    with pytest.raises(ValorFueraDeRango, match="80"):
        Usuario(**datos(nombre="x" * 81))
    with pytest.raises(ValorFueraDeRango, match="120"):
        Usuario(**datos(apellidos="x" * 121))


def test_correo_invalido():
    with pytest.raises(FormatoInvalido):
        Usuario(**datos(correo="no-es-correo"))


def test_hash_demasiado_corto():
    with pytest.raises(FormatoInvalido):
        Usuario(**datos(password_hash="1234"))


@pytest.mark.parametrize("estado", [0, 33])
def test_estado_fuera_de_rango(estado):
    with pytest.raises(ValorFueraDeRango):
        Usuario(**datos(estado_id=estado))


def test_rol_admin():
    admin = Usuario(**datos(rol=" ADMIN "))
    assert admin.rol == "admin"
    assert admin.es_admin is True


def test_rol_invalido():
    with pytest.raises(OpcionNoPermitida):
        Usuario(**datos(rol="superusuario"))


@pytest.mark.parametrize("valor", [1, 0, "si", None])
def test_activo_debe_ser_booleano(valor):
    with pytest.raises(TipoDeDatoInvalido):
        Usuario(**datos(activo=valor))


def test_desactivar_y_activar(usuario):
    usuario.desactivar()
    assert usuario.activo is False
    usuario.activar()
    assert usuario.activo is True


def test_los_setters_validan_y_limpian(usuario):
    usuario.nombre = "  María  "
    usuario.correo = " NUEVO@Correo.com "
    usuario.estado_id = "5"
    usuario.rol = "admin"
    assert usuario.nombre == "María"
    assert usuario.correo == "nuevo@correo.com"
    assert usuario.estado_id == 5
    assert usuario.es_admin


def test_un_cambio_invalido_conserva_el_valor_anterior(usuario):
    with pytest.raises(FormatoInvalido):
        usuario.correo = "malo"
    assert usuario.correo == "ana.lopez@correo.com"
    with pytest.raises(ErrorDeValidacion):
        usuario.estado_id = 99
    assert usuario.estado_id == 1


def test_cambiar_el_hash(usuario):
    nuevo = "scrypt$" + "b" * 40
    usuario.cambiar_password_hash(nuevo)
    assert usuario.password_hash == nuevo
    with pytest.raises(FormatoInvalido):
        usuario.cambiar_password_hash("corto")
    assert usuario.password_hash == nuevo


def test_la_region_y_el_id_no_cambian(usuario):
    with pytest.raises(AttributeError):
        usuario.region_id = 3
    with pytest.raises(AttributeError):
        usuario.usuario_id = UUID(ID)


def test_igualdad_por_region_e_id(usuario):
    mismo = Usuario(**datos(usuario_id=ID, nombre="Otro nombre"))
    otra_region = Usuario(**datos(usuario_id=ID, region_id=3))
    assert usuario == mismo
    assert hash(usuario) == hash(mismo)
    assert usuario != otra_region
    assert usuario != "usuario"
    assert len({usuario, mismo, otra_region}) == 2


def test_repr_no_expone_correo_ni_hash(usuario):
    texto = repr(usuario)
    assert ID in texto
    assert "correo" not in texto.lower().replace("usuario(", "")
    assert "ana.lopez" not in texto
    assert HASH not in texto
    assert "scrypt" not in texto
