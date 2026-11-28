"""Usuario de la aplicación."""

from uuid import UUID, uuid4

from plantas.dominio.catalogos import ROLES
from plantas.dominio.validaciones import (
    validar_booleano,
    validar_correo,
    validar_estado_id,
    validar_opcion,
    validar_password_hash,
    validar_region,
    validar_texto_no_vacio,
    validar_uuid,
)


class Usuario:
    """Una persona registrada, ubicada en una región.

    Guarda el hash de la contraseña, nunca la contraseña. El hash y el correo
    no aparecen en ``repr`` para que no lleguen a los registros por accidente.
    La API genera el ``usuario_id`` al dar de alta (D-01, sección 6).
    """

    def __init__(
        self,
        *,
        region_id: int,
        nombre: str,
        apellidos: str,
        correo: str,
        password_hash: str,
        estado_id: int,
        rol: str = "usuario",
        activo: bool = True,
        usuario_id: UUID | str | None = None,
    ) -> None:
        self._region_id = validar_region(region_id)
        self._usuario_id = (
            uuid4()
            if usuario_id is None
            else validar_uuid(usuario_id, "usuario_id")
        )
        self.nombre = nombre
        self.apellidos = apellidos
        self.correo = correo
        self.cambiar_password_hash(password_hash)
        self.estado_id = estado_id
        self.rol = rol
        self._activo = validar_booleano(activo, "activo")

    @property
    def region_id(self) -> int:
        return self._region_id

    @property
    def usuario_id(self) -> UUID:
        return self._usuario_id

    @property
    def nombre(self) -> str:
        return self._nombre

    @nombre.setter
    def nombre(self, valor: str) -> None:
        self._nombre = validar_texto_no_vacio(valor, "nombre", 80)

    @property
    def apellidos(self) -> str:
        return self._apellidos

    @apellidos.setter
    def apellidos(self, valor: str) -> None:
        self._apellidos = validar_texto_no_vacio(valor, "apellidos", 120)

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombre} {self.apellidos}"

    @property
    def correo(self) -> str:
        return self._correo

    @correo.setter
    def correo(self, valor: str) -> None:
        self._correo = validar_correo(valor)

    @property
    def password_hash(self) -> str:
        return self._password_hash

    def cambiar_password_hash(self, nuevo_hash: str) -> None:
        self._password_hash = validar_password_hash(nuevo_hash)

    @property
    def estado_id(self) -> int:
        return self._estado_id

    @estado_id.setter
    def estado_id(self, valor: int) -> None:
        self._estado_id = validar_estado_id(valor)

    @property
    def rol(self) -> str:
        return self._rol

    @rol.setter
    def rol(self, valor: str) -> None:
        self._rol = validar_opcion(valor, "rol", ROLES)

    @property
    def es_admin(self) -> bool:
        return self._rol == "admin"

    @property
    def activo(self) -> bool:
        return self._activo

    def desactivar(self) -> None:
        self._activo = False

    def activar(self) -> None:
        self._activo = True

    def __eq__(self, otro: object) -> bool:
        if not isinstance(otro, Usuario):
            return NotImplemented
        return (self.region_id, self.usuario_id) == (
            otro.region_id,
            otro.usuario_id,
        )

    def __hash__(self) -> int:
        return hash((self.region_id, self.usuario_id))

    def __repr__(self) -> str:
        return (
            f"Usuario(usuario_id={self.usuario_id}, "
            f"region_id={self.region_id}, rol={self.rol!r})"
        )
