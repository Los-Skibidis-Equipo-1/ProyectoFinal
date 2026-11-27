"""Jerarquía de excepciones de la aplicación.

Todas heredan de ErrorPlantas, así que una capa de arriba (la API) puede
atrapar ErrorPlantas para cualquier error propio y dejar que los errores
inesperados sigan su camino.

    ErrorPlantas
    ├── ErrorDeValidacion          dato mal formado o fuera de lo permitido
    │   ├── CampoVacio
    │   ├── TipoDeDatoInvalido
    │   ├── ValorFueraDeRango
    │   ├── OpcionNoPermitida
    │   └── FechaInvalida
    └── ErrorDeNegocio             dato válido que la regla no permite
        ├── PlantaNoEncontrada
        └── PlantaInactiva

El atributo ``sqlstate`` relaciona cada excepción con el error que devuelve
PostgreSQL en el procedimiento sp_registrar_riego (A5), para que la capa de
datos (B9) traduzca el error de la base a la excepción correcta.

Los mensajes y los atributos no deben llevar contraseñas, tokens ni datos
personales: se escriben en la bitácora y en las respuestas de la API.
"""


class ErrorPlantas(Exception):  # noqa: N818 (en español: prefijo Error)
    """Base de todas las excepciones propias de la aplicación."""

    sqlstate: str | None = None

    def __init__(self, mensaje: str) -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje


class ErrorDeValidacion(ErrorPlantas):
    """Un dato no cumple el formato o los límites permitidos."""

    sqlstate = "23514"  # check_violation

    def __init__(
        self,
        mensaje: str,
        campo: str | None = None,
        valor: object = None,
    ) -> None:
        super().__init__(mensaje)
        self.campo = campo
        self.valor = valor


class CampoVacio(ErrorDeValidacion):
    """Un campo obligatorio llegó vacío o solo con espacios."""


class TipoDeDatoInvalido(ErrorDeValidacion):
    """El dato no es del tipo esperado (por ejemplo, texto y no número)."""


class ValorFueraDeRango(ErrorDeValidacion):
    """El valor es del tipo correcto pero queda fuera de los límites."""


class OpcionNoPermitida(ErrorDeValidacion):
    """El valor no está entre las opciones válidas de un catálogo."""


class FechaInvalida(ErrorDeValidacion):
    """La fecha está vacía, no tiene zona horaria o es futura."""


class ErrorDeNegocio(ErrorPlantas):
    """El dato es válido, pero una regla del sistema no permite la acción."""


class PlantaNoEncontrada(ErrorDeNegocio):
    """La planta no existe en esa región."""

    sqlstate = "P0002"  # no_data_found

    def __init__(self, planta_id: int, region_id: int) -> None:
        super().__init__(
            f"La planta {planta_id} no existe en la región {region_id}"
        )
        self.planta_id = planta_id
        self.region_id = region_id


class PlantaInactiva(ErrorDeNegocio):
    """La planta existe, pero ya no está activa (fallecida o regalada)."""

    sqlstate = "23514"  # check_violation

    def __init__(self, planta_id: int, estatus: str) -> None:
        super().__init__(
            f"La planta {planta_id} no está activa (estatus: {estatus})"
        )
        self.planta_id = planta_id
        self.estatus = estatus
