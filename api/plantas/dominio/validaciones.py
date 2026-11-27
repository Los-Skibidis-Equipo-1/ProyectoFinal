"""Validaciones de datos del dominio.

Cada función devuelve el dato ya limpio y convertido, o lanza una subclase de
ErrorDeValidacion con un mensaje que dice qué campo falló y por qué. Las
reglas replican las del esquema (db/01_esquema.sql) y las de sp_registrar_riego
(A5), para que un dato inválido se rechace en la API antes de llegar a la base.
"""

import math
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from plantas.dominio.catalogos import (
    HUMEDAD_MAX,
    HUMEDAD_MIN,
    REGION_MAX,
    REGION_MIN,
    RIEGO_DIAS_MAX,
    RIEGO_DIAS_MIN,
    TEMPERATURA_MAX,
    TEMPERATURA_MIN,
)
from plantas.dominio.excepciones import (
    CampoVacio,
    ErrorDeValidacion,
    FechaInvalida,
    OpcionNoPermitida,
    TipoDeDatoInvalido,
    ValorFueraDeRango,
)


def convertir_a_numero(valor: object, campo: str) -> float:
    """Convierte un número o un texto como ``"45,5"`` a ``float``.

    Acepta coma o punto decimal, porque los sensores y los archivos CSV
    pueden usar cualquiera. Rechaza los booleanos, que en Python son enteros
    (``True == 1``), y los valores no finitos (``nan`` e ``inf``).
    """
    if isinstance(valor, bool):
        raise TipoDeDatoInvalido(
            f"{campo} debe ser un número, no un booleano", campo, valor
        )
    if isinstance(valor, int | float):
        numero = float(valor)
    elif isinstance(valor, str):
        try:
            numero = float(valor.strip().replace(",", "."))
        except ValueError as error:
            raise TipoDeDatoInvalido(
                f"{campo} debe ser un número (recibido: {valor!r})",
                campo,
                valor,
            ) from error
    else:
        raise TipoDeDatoInvalido(
            f"{campo} debe ser un número (tipo recibido: "
            f"{type(valor).__name__})",
            campo,
            valor,
        )
    if not math.isfinite(numero):
        raise TipoDeDatoInvalido(
            f"{campo} debe ser un número finito", campo, valor
        )
    return numero


def validar_texto_no_vacio(
    valor: object, campo: str, largo_maximo: int | None = None
) -> str:
    """Devuelve el texto sin espacios en los extremos; no puede estar vacío."""
    if not isinstance(valor, str):
        raise TipoDeDatoInvalido(
            f"{campo} debe ser texto (tipo recibido: {type(valor).__name__})",
            campo,
            valor,
        )
    texto = valor.strip()
    if not texto:
        raise CampoVacio(f"{campo} no puede estar vacío", campo, valor)
    if largo_maximo is not None and len(texto) > largo_maximo:
        raise ValorFueraDeRango(
            f"{campo} no puede tener más de {largo_maximo} caracteres",
            campo,
            valor,
        )
    return texto


def validar_rango(
    valor: object, campo: str, minimo: float, maximo: float
) -> float:
    """Convierte a número y comprueba que esté entre mínimo y máximo."""
    numero = convertir_a_numero(valor, campo)
    if not minimo <= numero <= maximo:
        raise ValorFueraDeRango(
            f"{campo} debe estar entre {minimo} y {maximo} "
            f"(recibido: {numero})",
            campo,
            valor,
        )
    return numero


def validar_humedad(valor: object) -> float:
    """Humedad en porcentaje, de 0 a 100 (ck_planta_humedad)."""
    return validar_rango(valor, "humedad", HUMEDAD_MIN, HUMEDAD_MAX)


def validar_temperatura(valor: object) -> float:
    """Temperatura en grados Celsius, de -20 a 60 (ck_especie_temp_rango)."""
    return validar_rango(
        valor, "temperatura", TEMPERATURA_MIN, TEMPERATURA_MAX
    )


def validar_cantidad_agua_ml(valor: object) -> float:
    """Cantidad de agua en mililitros; debe ser mayor que 0 (A5)."""
    numero = convertir_a_numero(valor, "cantidad de agua")
    if numero <= 0:
        raise ValorFueraDeRango(
            f"La cantidad de agua debe ser mayor que 0 (recibido: {numero})",
            "cantidad de agua",
            valor,
        )
    return numero


def validar_frecuencia_riego_dias(valor: object) -> int:
    """Días entre riegos: un entero de 1 a 365 (ck_especie_riego)."""
    numero = validar_rango(
        valor, "frecuencia de riego", RIEGO_DIAS_MIN, RIEGO_DIAS_MAX
    )
    if not numero.is_integer():
        raise TipoDeDatoInvalido(
            f"La frecuencia de riego debe ser un número entero de días "
            f"(recibido: {numero})",
            "frecuencia de riego",
            valor,
        )
    return int(numero)


def validar_opcion(valor: object, campo: str, opciones: Iterable[str]) -> str:
    """Comprueba que el texto sea una de las opciones permitidas.

    Quita espacios y pasa a minúsculas, como están guardadas en la base.
    """
    opciones = tuple(opciones)
    texto = validar_texto_no_vacio(valor, campo).lower()
    if texto not in opciones:
        raise OpcionNoPermitida(
            f"{campo} debe ser una de {', '.join(opciones)} "
            f"(recibido: {texto!r})",
            campo,
            valor,
        )
    return texto


def validar_fecha_no_futura(
    valor: object, campo: str, ahora: datetime | None = None
) -> datetime:
    """La fecha debe traer zona horaria y no estar en el futuro (A5).

    ``ahora`` se puede pasar para probar sin depender del reloj.
    """
    if not isinstance(valor, datetime):
        raise FechaInvalida(f"{campo} no puede estar vacía", campo, valor)
    if valor.tzinfo is None:
        raise FechaInvalida(f"{campo} debe incluir zona horaria", campo, valor)
    referencia = ahora if ahora is not None else datetime.now(UTC)
    if valor > referencia:
        raise FechaInvalida(
            f"{campo} no puede estar en el futuro", campo, valor
        )
    return valor


def validar_region(valor: object) -> int:
    """Región del usuario: 1 Norte, 2 Centro o 3 Sur (ck_region_id)."""
    numero = validar_rango(valor, "región", REGION_MIN, REGION_MAX)
    if not numero.is_integer():
        raise TipoDeDatoInvalido(
            f"La región debe ser un número entero (recibido: {numero})",
            "región",
            valor,
        )
    return int(numero)


def validar_uuid(valor: object, campo: str) -> UUID:
    """Identificador UUID, como los de usuario, planta y sensor.

    La API genera el ``usuario_id`` (D-01, sección 6); los demás los genera
    la base. Acepta un UUID o su texto.
    """
    if isinstance(valor, UUID):
        return valor
    if not isinstance(valor, str):
        raise TipoDeDatoInvalido(
            f"{campo} debe ser un UUID (tipo recibido: "
            f"{type(valor).__name__})",
            campo,
            valor,
        )
    try:
        return UUID(valor.strip())
    except ValueError as error:
        raise TipoDeDatoInvalido(
            f"{campo} no es un UUID válido", campo, valor
        ) from error


@dataclass
class ResultadoLecturas:
    """Resumen de un lote de lecturas: las buenas y las que se rechazaron."""

    validas: list[float] = field(default_factory=list)
    errores: list[tuple[int, str]] = field(default_factory=list)
    procesadas: int = 0


def procesar_lecturas_humedad(lecturas: Iterable[object]) -> ResultadoLecturas:
    """Valida un lote de lecturas de humedad sin detenerse en la primera falla.

    Es el patrón que se usará al leer archivos CSV y JSON (B7) y en el
    simulador de sensores (B15): una lectura mala no tira el lote completo.

    - ``try``: intenta convertir y validar la lectura.
    - ``except``: si falla, guarda la posición y el motivo.
    - ``else``: solo si no hubo error, guarda la lectura como válida.
    - ``finally``: siempre cuenta la lectura como procesada.
    """
    resultado = ResultadoLecturas()
    for posicion, lectura in enumerate(lecturas, start=1):
        try:
            humedad = validar_humedad(lectura)
        except ErrorDeValidacion as error:
            resultado.errores.append((posicion, error.mensaje))
        else:
            resultado.validas.append(humedad)
        finally:
            resultado.procesadas += 1
    return resultado
