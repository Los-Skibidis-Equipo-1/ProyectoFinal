"""Planta de un usuario."""

from datetime import date, datetime
from uuid import UUID, uuid4

from plantas.dominio.catalogos import ESTATUS_PLANTA, TIPOS_ESPACIO
from plantas.dominio.excepciones import ErrorDeValidacion, PlantaInactiva
from plantas.dominio.validaciones import (
    validar_booleano,
    validar_entero_positivo,
    validar_fecha_calendario_no_futura,
    validar_fecha_no_futura,
    validar_humedad,
    validar_opcion,
    validar_region,
    validar_texto_no_vacio,
    validar_texto_opcional,
    validar_uuid,
)


class Planta:
    """Una planta que pertenece a un usuario y a una especie.

    La humedad actual solo existe si hay una lectura: ``humedad_actual`` y
    ``fecha_ultima_lectura`` van juntas o ninguna (ck_planta_lectura).

    ``tiene_sensor_humedad`` es un dato calculado por la capa de datos (hay un
    sensor activo de tipo humedad para esta planta) y no se guarda en la base.
    Si es ``False``, la aplicación deshabilita las funciones de humedad. Es el
    acuerdo de «sensores opcionales» del documento de contexto, sección 5.
    """

    def __init__(
        self,
        *,
        region_id: int,
        usuario_id: UUID | str,
        especie_id: int,
        apodo: str,
        tipo_espacio: str,
        ubicacion_descripcion: str | None = None,
        fecha_adquisicion: date | None = None,
        estatus: str = "activa",
        humedad_actual: float | None = None,
        fecha_ultima_lectura: datetime | None = None,
        tiene_sensor_humedad: bool = False,
        planta_id: UUID | str | None = None,
        ahora: datetime | None = None,
        hoy: date | None = None,
    ) -> None:
        self._region_id = validar_region(region_id)
        self._usuario_id = validar_uuid(usuario_id, "usuario_id")
        self._especie_id = validar_entero_positivo(especie_id, "especie_id")
        self._planta_id = (
            uuid4()
            if planta_id is None
            else validar_uuid(planta_id, "planta_id")
        )
        self.apodo = apodo
        self.tipo_espacio = tipo_espacio
        self.ubicacion_descripcion = ubicacion_descripcion
        self._fecha_adquisicion = None
        if fecha_adquisicion is not None:
            self._fecha_adquisicion = validar_fecha_calendario_no_futura(
                fecha_adquisicion, "fecha de adquisición", hoy
            )
        self._estatus = validar_opcion(estatus, "estatus", ESTATUS_PLANTA)
        self._tiene_sensor_humedad = validar_booleano(
            tiene_sensor_humedad, "tiene_sensor_humedad"
        )
        self._humedad_actual: float | None = None
        self._fecha_ultima_lectura: datetime | None = None
        if (humedad_actual is None) != (fecha_ultima_lectura is None):
            raise ErrorDeValidacion(
                "La humedad actual y la fecha de la última lectura van "
                "juntas o ninguna",
                "humedad_actual",
            )
        if humedad_actual is not None and fecha_ultima_lectura is not None:
            self.registrar_lectura_humedad(
                humedad_actual, fecha_ultima_lectura, ahora
            )

    # --- identificadores: no cambian --------------------------------------

    @property
    def region_id(self) -> int:
        return self._region_id

    @property
    def planta_id(self) -> UUID:
        return self._planta_id

    @property
    def usuario_id(self) -> UUID:
        return self._usuario_id

    @property
    def especie_id(self) -> int:
        return self._especie_id

    # --- datos que se pueden cambiar --------------------------------------

    @property
    def apodo(self) -> str:
        return self._apodo

    @apodo.setter
    def apodo(self, valor: str) -> None:
        self._apodo = validar_texto_no_vacio(valor, "apodo", 60)

    @property
    def tipo_espacio(self) -> str:
        return self._tipo_espacio

    @tipo_espacio.setter
    def tipo_espacio(self, valor: str) -> None:
        self._tipo_espacio = validar_opcion(
            valor, "tipo de espacio", TIPOS_ESPACIO
        )

    @property
    def ubicacion_descripcion(self) -> str | None:
        return self._ubicacion_descripcion

    @ubicacion_descripcion.setter
    def ubicacion_descripcion(self, valor: str | None) -> None:
        self._ubicacion_descripcion = validar_texto_opcional(
            valor, "ubicación", 100
        )

    @property
    def fecha_adquisicion(self) -> date | None:
        return self._fecha_adquisicion

    # --- estatus ----------------------------------------------------------

    @property
    def estatus(self) -> str:
        return self._estatus

    @property
    def esta_activa(self) -> bool:
        return self._estatus == "activa"

    def cambiar_estatus(self, nuevo: str) -> None:
        self._estatus = validar_opcion(nuevo, "estatus", ESTATUS_PLANTA)

    def verificar_activa(self) -> None:
        """Lanza ``PlantaInactiva`` si la planta ya no está activa.

        Es la misma regla que aplica sp_registrar_riego (A5).
        """
        if not self.esta_activa:
            raise PlantaInactiva(self.planta_id, self.estatus)

    # --- humedad y sensor -------------------------------------------------

    @property
    def humedad_actual(self) -> float | None:
        return self._humedad_actual

    @property
    def fecha_ultima_lectura(self) -> datetime | None:
        return self._fecha_ultima_lectura

    @property
    def tiene_sensor_humedad(self) -> bool:
        return self._tiene_sensor_humedad

    def marcar_sensor_humedad(self, tiene: bool) -> None:
        """La capa de datos lo actualiza al saber si hay un sensor activo."""
        self._tiene_sensor_humedad = validar_booleano(
            tiene, "tiene_sensor_humedad"
        )

    def registrar_lectura_humedad(
        self,
        humedad: float,
        fecha_hora: datetime,
        ahora: datetime | None = None,
    ) -> None:
        """Guarda la última lectura. Valida las dos cosas antes de cambiar."""
        valor = validar_humedad(humedad)
        fecha = validar_fecha_no_futura(
            fecha_hora, "fecha de la lectura", ahora
        )
        self._humedad_actual = valor
        self._fecha_ultima_lectura = fecha

    # --- identidad --------------------------------------------------------

    def __eq__(self, otra: object) -> bool:
        if not isinstance(otra, Planta):
            return NotImplemented
        return (self.region_id, self.planta_id) == (
            otra.region_id,
            otra.planta_id,
        )

    def __hash__(self) -> int:
        return hash((self.region_id, self.planta_id))

    def __repr__(self) -> str:
        return (
            f"Planta(planta_id={self.planta_id}, "
            f"region_id={self.region_id}, estatus={self.estatus!r})"
        )
