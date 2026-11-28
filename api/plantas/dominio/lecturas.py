"""Lecturas de sensores: una clase base y un tipo por cada sensor.

``LecturaSensor`` define lo común (qué sensor, qué planta, cuándo) y los
métodos que cada tipo implementa a su manera. ``LecturaHumedad`` y
``LecturaAmbiente`` heredan de ella. Quien usa una lectura no necesita saber
de qué tipo es: llama ``a_documento()``, ``resumen()`` o
``humedad_para_planta()`` y cada clase responde a su manera (polimorfismo).

Los documentos tienen la forma que usa MongoDB (ver requerimientos de datos):
``sensor_id``, ``planta_id``, ``region_id``, ``tipo``, ``timestamp`` y las
medidas del tipo. Los UUID se guardan como texto.
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import ClassVar
from uuid import UUID

from plantas.dominio.catalogos import (
    HUMEDAD_MAX,
    HUMEDAD_MIN,
    TEMPERATURA_MAX,
    TEMPERATURA_MIN,
)
from plantas.dominio.excepciones import (
    CampoVacio,
    LecturaFueraDeRango,
    OpcionNoPermitida,
)
from plantas.dominio.validaciones import (
    convertir_a_numero,
    validar_fecha_no_futura,
    validar_region,
    validar_uuid,
)


def _validar_medida(
    valor: object, campo: str, minimo: float, maximo: float
) -> float:
    """Convierte la medida a número y exige que esté dentro de su rango.

    Un texto que no es número sigue siendo ``TipoDeDatoInvalido``; un número
    fuera de rango es ``LecturaFueraDeRango``.
    """
    numero = convertir_a_numero(valor, campo)
    if not minimo <= numero <= maximo:
        raise LecturaFueraDeRango(
            f"{campo} debe estar entre {minimo} y {maximo} "
            f"(recibido: {numero})",
            campo,
            valor,
        )
    return numero


class LecturaSensor(ABC):
    """Una medida tomada por un sensor en un momento dado.

    Una lectura es un hecho del pasado: todos sus datos son de solo lectura.
    Cada subclase concreta define ``tipo`` (``"humedad"`` o ``"ambiente"``) y
    se registra sola para que ``desde_documento`` sepa cuál crear.
    """

    tipo: ClassVar[str]
    _registro: ClassVar[dict[str, type["LecturaSensor"]]] = {}

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        tipo = cls.__dict__.get("tipo")
        if tipo is not None:
            LecturaSensor._registro[tipo] = cls

    def __init__(
        self,
        *,
        sensor_id: UUID | str,
        planta_id: UUID | str,
        region_id: int,
        timestamp: datetime | None = None,
        ahora: datetime | None = None,
    ) -> None:
        self._sensor_id = validar_uuid(sensor_id, "sensor_id")
        self._planta_id = validar_uuid(planta_id, "planta_id")
        self._region_id = validar_region(region_id)
        momento = datetime.now(UTC) if timestamp is None else timestamp
        self._timestamp = validar_fecha_no_futura(
            momento, "timestamp de la lectura", ahora
        )

    @property
    def sensor_id(self) -> UUID:
        return self._sensor_id

    @property
    def planta_id(self) -> UUID:
        return self._planta_id

    @property
    def region_id(self) -> int:
        return self._region_id

    @property
    def timestamp(self) -> datetime:
        return self._timestamp

    # --- lo que cada tipo define a su manera ------------------------------

    @abstractmethod
    def _medidas(self) -> dict[str, float]:
        """Las medidas propias del tipo, con los nombres del documento."""

    @abstractmethod
    def resumen(self) -> str:
        """Una frase legible con la medida, para bitácoras y mensajes."""

    def humedad_para_planta(self) -> float | None:
        """Humedad del suelo que debe pasar a ``planta.humedad_actual``.

        Solo las lecturas de humedad del suelo la tienen; las demás
        devuelven ``None`` y la API no toca la planta (acuerdo base-API).
        """
        return None

    # --- lo común ---------------------------------------------------------

    def a_documento(self) -> dict[str, object]:
        """Documento listo para guardar en MongoDB."""
        return {
            "sensor_id": str(self.sensor_id),
            "planta_id": str(self.planta_id),
            "region_id": self.region_id,
            "tipo": self.tipo,
            "timestamp": self.timestamp,
            **self._medidas(),
        }

    @staticmethod
    def desde_documento(documento: Mapping[str, object]) -> "LecturaSensor":
        """Crea la lectura del tipo correcto a partir de un documento.

        MongoDB devuelve las fechas sin zona horaria (siempre en UTC), así que
        aquí se les pone UTC antes de validarlas.
        """
        tipo = documento.get("tipo")
        clase = (
            LecturaSensor._registro.get(tipo)
            if isinstance(tipo, str)
            else None
        )
        if clase is None:
            raise OpcionNoPermitida(
                "tipo de lectura debe ser una de "
                f"{', '.join(sorted(LecturaSensor._registro))} "
                f"(recibido: {tipo!r})",
                "tipo",
                tipo,
            )
        timestamp = documento.get("timestamp")
        if isinstance(timestamp, datetime) and timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        comunes = {
            "sensor_id": documento.get("sensor_id"),
            "planta_id": documento.get("planta_id"),
            "region_id": documento.get("region_id"),
            "timestamp": timestamp,
        }
        faltantes = [
            campo for campo, valor in comunes.items() if valor is None
        ]
        if faltantes:
            raise CampoVacio(
                f"Al documento le falta: {', '.join(faltantes)}",
                faltantes[0],
            )
        return clase._desde_medidas(comunes, documento)

    @classmethod
    @abstractmethod
    def _desde_medidas(
        cls, comunes: dict[str, object], documento: Mapping[str, object]
    ) -> "LecturaSensor":
        """Crea la lectura con los datos comunes y las medidas del tipo."""

    def __eq__(self, otra: object) -> bool:
        if not isinstance(otra, LecturaSensor):
            return NotImplemented
        return self.a_documento() == otra.a_documento()

    def __hash__(self) -> int:
        return hash((self.tipo, self.sensor_id, self.timestamp))

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(sensor_id={self.sensor_id}, "
            f"timestamp={self.timestamp.isoformat()})"
        )


def _exigir(documento: Mapping[str, object], campo: str) -> object:
    valor = documento.get(campo)
    if valor is None:
        raise CampoVacio(f"Al documento le falta {campo}", campo)
    return valor


class LecturaHumedad(LecturaSensor):
    """Humedad del suelo, en porcentaje de 0 a 100."""

    tipo = "humedad"

    def __init__(self, *, humedad_suelo_pct: float, **comunes: object) -> None:
        super().__init__(**comunes)  # type: ignore[arg-type]
        self._humedad_suelo_pct = _validar_medida(
            humedad_suelo_pct, "humedad del suelo", HUMEDAD_MIN, HUMEDAD_MAX
        )

    @property
    def humedad_suelo_pct(self) -> float:
        return self._humedad_suelo_pct

    def _medidas(self) -> dict[str, float]:
        return {"humedad_suelo_pct": self._humedad_suelo_pct}

    def resumen(self) -> str:
        return f"Humedad del suelo: {self._humedad_suelo_pct:g} %"

    def humedad_para_planta(self) -> float | None:
        return self._humedad_suelo_pct

    @classmethod
    def _desde_medidas(
        cls, comunes: dict[str, object], documento: Mapping[str, object]
    ) -> "LecturaHumedad":
        return cls(
            humedad_suelo_pct=_exigir(documento, "humedad_suelo_pct"),  # type: ignore[arg-type]
            **comunes,
        )


class LecturaAmbiente(LecturaSensor):
    """Temperatura del aire (°C) y humedad relativa (%)."""

    tipo = "ambiente"

    def __init__(
        self,
        *,
        temperatura_c: float,
        humedad_relativa_pct: float,
        **comunes: object,
    ) -> None:
        super().__init__(**comunes)  # type: ignore[arg-type]
        self._temperatura_c = _validar_medida(
            temperatura_c, "temperatura", TEMPERATURA_MIN, TEMPERATURA_MAX
        )
        self._humedad_relativa_pct = _validar_medida(
            humedad_relativa_pct, "humedad relativa", HUMEDAD_MIN, HUMEDAD_MAX
        )

    @property
    def temperatura_c(self) -> float:
        return self._temperatura_c

    @property
    def humedad_relativa_pct(self) -> float:
        return self._humedad_relativa_pct

    def _medidas(self) -> dict[str, float]:
        return {
            "temperatura_c": self._temperatura_c,
            "humedad_relativa_pct": self._humedad_relativa_pct,
        }

    def resumen(self) -> str:
        return (
            f"Temperatura: {self._temperatura_c:g} °C, "
            f"humedad relativa: {self._humedad_relativa_pct:g} %"
        )

    @classmethod
    def _desde_medidas(
        cls, comunes: dict[str, object], documento: Mapping[str, object]
    ) -> "LecturaAmbiente":
        return cls(
            temperatura_c=_exigir(documento, "temperatura_c"),  # type: ignore[arg-type]
            humedad_relativa_pct=_exigir(documento, "humedad_relativa_pct"),  # type: ignore[arg-type]
            **comunes,
        )
