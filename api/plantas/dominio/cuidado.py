"""Registro de un cuidado hecho a una planta."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from plantas.dominio.catalogos import TIPOS_CUIDADO
from plantas.dominio.excepciones import ErrorDeValidacion
from plantas.dominio.validaciones import (
    validar_cantidad_agua_ml,
    validar_fecha_no_futura,
    validar_opcion,
    validar_region,
    validar_texto_opcional,
    validar_uuid,
)


class Cuidado:
    """Algo que se le hizo a una planta: riego, fertilizado, poda…

    Un cuidado es un hecho del pasado, así que no se modifica: todos sus
    datos son de solo lectura. Solo un riego puede llevar cantidad de agua
    (ck_cuidado_cantidad). La fecha no puede ser futura.
    """

    def __init__(
        self,
        *,
        region_id: int,
        planta_id: UUID | str,
        tipo: str,
        fecha_hora: datetime | None = None,
        cantidad_ml: int | None = None,
        notas: str | None = None,
        cuidado_id: UUID | str | None = None,
        ahora: datetime | None = None,
    ) -> None:
        self._region_id = validar_region(region_id)
        self._planta_id = validar_uuid(planta_id, "planta_id")
        self._cuidado_id = (
            uuid4()
            if cuidado_id is None
            else validar_uuid(cuidado_id, "cuidado_id")
        )
        self._tipo = validar_opcion(tipo, "tipo de cuidado", TIPOS_CUIDADO)
        momento = datetime.now(UTC) if fecha_hora is None else fecha_hora
        self._fecha_hora = validar_fecha_no_futura(
            momento, "fecha del cuidado", ahora
        )
        self._cantidad_ml = self._validar_cantidad(cantidad_ml)
        self._notas = validar_texto_opcional(notas, "notas", 500)

    def _validar_cantidad(self, cantidad_ml: object) -> int | None:
        if cantidad_ml is None:
            return None
        if self._tipo != "riego":
            raise ErrorDeValidacion(
                "Solo un riego puede llevar cantidad de agua",
                "cantidad de agua",
            )
        return validar_cantidad_agua_ml(cantidad_ml)

    @classmethod
    def riego(
        cls,
        *,
        region_id: int,
        planta_id: UUID | str,
        cantidad_ml: int | None = None,
        notas: str | None = None,
        fecha_hora: datetime | None = None,
        ahora: datetime | None = None,
    ) -> "Cuidado":
        """Atajo para el cuidado más común."""
        return cls(
            region_id=region_id,
            planta_id=planta_id,
            tipo="riego",
            fecha_hora=fecha_hora,
            cantidad_ml=cantidad_ml,
            notas=notas,
            ahora=ahora,
        )

    @property
    def region_id(self) -> int:
        return self._region_id

    @property
    def cuidado_id(self) -> UUID:
        return self._cuidado_id

    @property
    def planta_id(self) -> UUID:
        return self._planta_id

    @property
    def tipo(self) -> str:
        return self._tipo

    @property
    def fecha_hora(self) -> datetime:
        return self._fecha_hora

    @property
    def cantidad_ml(self) -> int | None:
        return self._cantidad_ml

    @property
    def notas(self) -> str | None:
        return self._notas

    @property
    def es_riego(self) -> bool:
        return self._tipo == "riego"

    def __eq__(self, otro: object) -> bool:
        if not isinstance(otro, Cuidado):
            return NotImplemented
        return (self.region_id, self.cuidado_id) == (
            otro.region_id,
            otro.cuidado_id,
        )

    def __hash__(self) -> int:
        return hash((self.region_id, self.cuidado_id))

    def __repr__(self) -> str:
        return (
            f"Cuidado(cuidado_id={self.cuidado_id}, "
            f"tipo={self.tipo!r}, planta_id={self.planta_id})"
        )
