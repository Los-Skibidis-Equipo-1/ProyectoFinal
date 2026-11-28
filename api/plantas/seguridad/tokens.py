"""Tokens JWT de sesión (HS256) con expiración.

Un token se emite al iniciar sesión y la API lo recibe en cada petición.
Lleva estos datos (los dos primeros son los estándar de JWT):

- ``sub``: el ``usuario_id``.
- ``iat`` y ``exp``: cuándo se emitió y cuándo vence.
- ``iss``: quién lo emitió (``plantas-api``).
- ``jti``: un identificador único del token.
- ``reg`` y ``rol``: la región y el rol, para no consultar la base en cada
  petición (el rol se vuelve a comprobar en operaciones delicadas, B11).

Reglas que se siguen (RFC 8725, buenas prácticas de JWT):

- El algoritmo lo fija el servidor (``HS256``), nunca el que diga el token,
  así que ``alg: none`` y los cambios de algoritmo se rechazan.
- Los datos obligatorios deben estar y ``exp`` se comprueba siempre.
- La llave sale de la variable de entorno ``JWT_SECRET``, mide al menos 32
  caracteres y no puede ser el valor de ejemplo de ``.env.example``.
- Los errores son genéricos: no dicen qué parte del token falló ni lo
  repiten.

Un JWT va firmado, no cifrado: cualquiera puede leer lo que lleva. Por eso no
se guarda ninguna contraseña ni dato personal.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt

from plantas.dominio.catalogos import ROLES
from plantas.dominio.excepciones import (
    ConfiguracionInvalida,
    CredencialesInvalidas,
    ErrorDeValidacion,
    FechaInvalida,
    TokenExpirado,
    TokenInvalido,
)
from plantas.dominio.usuario import Usuario
from plantas.dominio.validaciones import (
    validar_region,
    validar_uuid,
)

ALGORITMO = "HS256"
EMISOR = "plantas-api"
VARIABLE_DE_LA_LLAVE = "JWT_SECRET"
DURACION_DEFECTO = timedelta(minutes=30)

CLAVE_LARGO_MINIMO = 32
# El valor de ejemplo de .env.example empieza así y nunca debe usarse.
_PREFIJO_DE_EJEMPLO = "cambiar"
# Un token normal mide unos 300 caracteres; uno enorme se descarta sin leerlo.
TOKEN_LARGO_MAXIMO = 2048

_DATOS_OBLIGATORIOS = ["exp", "iat", "iss", "sub", "jti", "reg", "rol"]


@dataclass(frozen=True)
class DatosDelToken:
    """Lo que dice un token ya verificado."""

    usuario_id: UUID
    region_id: int
    rol: str
    emitido: datetime
    expira: datetime
    token_id: UUID

    @property
    def es_admin(self) -> bool:
        return self.rol == "admin"


def _validar_clave(clave: object, origen: str) -> str:
    if not isinstance(clave, str) or not clave:
        raise ConfiguracionInvalida(origen, "falta la llave")
    if len(clave) < CLAVE_LARGO_MINIMO:
        raise ConfiguracionInvalida(
            origen, f"debe tener al menos {CLAVE_LARGO_MINIMO} caracteres"
        )
    if clave.startswith(_PREFIJO_DE_EJEMPLO):
        raise ConfiguracionInvalida(
            origen, "sigue con el valor de ejemplo de .env.example"
        )
    return clave


class ServicioDeTokens:
    """Emite y verifica los tokens de sesión.

    La llave se guarda en un atributo privado y no aparece en ``repr``.
    """

    def __init__(
        self,
        clave: str,
        *,
        duracion: timedelta = DURACION_DEFECTO,
        emisor: str = EMISOR,
    ) -> None:
        self._clave = _validar_clave(clave, VARIABLE_DE_LA_LLAVE)
        if not isinstance(duracion, timedelta) or duracion <= timedelta(0):
            raise ConfiguracionInvalida(
                "duración del token", "debe ser mayor que cero"
            )
        self._duracion = duracion
        self._emisor = emisor

    @classmethod
    def desde_entorno(
        cls, entorno: Mapping[str, str], **opciones: object
    ) -> "ServicioDeTokens":
        """Crea el servicio con la llave de ``JWT_SECRET``.

        Se le pasa ``os.environ``; así las pruebas no tocan el entorno real.
        """
        clave = _validar_clave(
            entorno.get(VARIABLE_DE_LA_LLAVE), VARIABLE_DE_LA_LLAVE
        )
        return cls(clave, **opciones)  # type: ignore[arg-type]

    @property
    def duracion(self) -> timedelta:
        return self._duracion

    def emitir(
        self, usuario: Usuario, *, ahora: datetime | None = None
    ) -> str:
        """Crea el token de un usuario que acaba de iniciar sesión.

        Una cuenta desactivada no recibe token. ``ahora`` solo se usa en las
        pruebas para emitir tokens de otra hora.
        """
        if not usuario.activo:
            raise CredencialesInvalidas
        momento = datetime.now(UTC) if ahora is None else ahora
        if momento.tzinfo is None:
            raise FechaInvalida(
                "La hora de emisión debe incluir zona horaria", "ahora"
            )
        emitido = int(momento.timestamp())
        datos = {
            "iss": self._emisor,
            "sub": str(usuario.usuario_id),
            "iat": emitido,
            "exp": emitido + int(self._duracion.total_seconds()),
            "jti": str(uuid4()),
            "reg": usuario.region_id,
            "rol": usuario.rol,
        }
        return jwt.encode(datos, self._clave, algorithm=ALGORITMO)

    def verificar(self, token: object) -> DatosDelToken:
        """Comprueba un token y devuelve lo que dice.

        Lanza ``TokenExpirado`` si ya venció y ``TokenInvalido`` por cualquier
        otra razón (firma, formato, datos que faltan o no son válidos).
        """
        if (
            not isinstance(token, str)
            or not token
            or len(token) > TOKEN_LARGO_MAXIMO
        ):
            raise TokenInvalido
        try:
            datos = jwt.decode(
                token,
                self._clave,
                algorithms=[ALGORITMO],
                issuer=self._emisor,
                options={"require": _DATOS_OBLIGATORIOS},
            )
        except jwt.ExpiredSignatureError:
            raise TokenExpirado from None
        except jwt.PyJWTError:
            raise TokenInvalido from None
        return self._leer_datos(datos)

    @staticmethod
    def _leer_datos(datos: Mapping[str, object]) -> DatosDelToken:
        # Los tipos deben ser exactamente los que se emitieron: un texto
        # donde va un entero, o un rol con otra forma, se rechaza.
        region, rol = datos["reg"], datos["rol"]
        if (
            not isinstance(datos["sub"], str)
            or not isinstance(datos["jti"], str)
            or not isinstance(region, int)
            or isinstance(region, bool)
            or rol not in ROLES
        ):
            raise TokenInvalido
        try:
            return DatosDelToken(
                usuario_id=validar_uuid(datos["sub"], "sub"),
                region_id=validar_region(region),
                rol=str(rol),
                emitido=datetime.fromtimestamp(datos["iat"], UTC),  # type: ignore[arg-type]
                expira=datetime.fromtimestamp(datos["exp"], UTC),  # type: ignore[arg-type]
                token_id=validar_uuid(datos["jti"], "jti"),
            )
        except (ErrorDeValidacion, TypeError, ValueError, OverflowError):
            raise TokenInvalido from None

    def __repr__(self) -> str:
        return (
            f"ServicioDeTokens(algoritmo={ALGORITMO!r}, "
            f"duracion={self._duracion})"
        )
