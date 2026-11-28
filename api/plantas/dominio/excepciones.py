"""Jerarquía de excepciones de la aplicación.

Todas heredan de ErrorPlantas, así que una capa de arriba (la API) puede
atrapar ErrorPlantas para cualquier error propio y dejar que los errores
inesperados sigan su camino.

    ErrorPlantas
    ├── ErrorDeValidacion          dato mal formado o fuera de lo permitido
    │   ├── CampoVacio
    │   ├── TipoDeDatoInvalido
    │   ├── ValorFueraDeRango
    │   │   └── LecturaFueraDeRango
    │   ├── OpcionNoPermitida
    │   ├── FormatoInvalido
    │   └── FechaInvalida
    ├── ErrorDeNegocio             dato válido que la regla no permite
    │   ├── PlantaNoEncontrada
    │   ├── PlantaInactiva
    │   ├── CorreoYaRegistrado
    │   └── ErrorDeAutenticacion   quién llama no pudo comprobar su identidad
    │       ├── CredencialesInvalidas
    │       └── TokenInvalido
    │           └── TokenExpirado
    └── ErrorDeInfraestructura     el dato está bien, pero un servicio falló
        ├── NodoNoDisponible
        ├── DirectorioNoDisponible
        ├── LecturaNoGuardada
        └── ConfiguracionInvalida

El atributo ``sqlstate`` relaciona cada excepción con el error que devuelve
PostgreSQL en el procedimiento sp_registrar_riego (A5), para que la capa de
datos (B9) traduzca el error de la base a la excepción correcta.

ErrorDeInfraestructura cubre lo que decidió D-01 (docs/registro-decisiones.md):
la API responde 503 si el directorio no confirma a tiempo, y reintenta las
lecturas de MongoDB antes de darlas por perdidas.

Los mensajes y los atributos no deben llevar contraseñas, tokens ni datos
personales (tampoco el correo, solo se guarda su HMAC): se escriben en la
bitácora y en las respuestas de la API.
"""

from uuid import UUID


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


class LecturaFueraDeRango(ValorFueraDeRango):
    """Una medida de un sensor cae fuera de lo físicamente posible.

    Hereda de ValorFueraDeRango, así que quien atrape esa excepción también
    atrapa esta, pero se puede distinguir una lectura mala de un dato mal
    capturado por una persona.
    """


class OpcionNoPermitida(ErrorDeValidacion):
    """El valor no está entre las opciones válidas de un catálogo."""


class FormatoInvalido(ErrorDeValidacion):
    """El texto no tiene el formato esperado (correo, hash de contraseña)."""


class FechaInvalida(ErrorDeValidacion):
    """La fecha está vacía, no tiene zona horaria o es futura."""


class ErrorDeNegocio(ErrorPlantas):
    """El dato es válido, pero una regla del sistema no permite la acción."""


class PlantaNoEncontrada(ErrorDeNegocio):
    """La planta no existe en esa región."""

    sqlstate = "P0002"  # no_data_found

    def __init__(self, planta_id: UUID, region_id: int) -> None:
        super().__init__(
            f"La planta {planta_id} no existe en la región {region_id}"
        )
        self.planta_id = planta_id
        self.region_id = region_id


class PlantaInactiva(ErrorDeNegocio):
    """La planta existe, pero ya no está activa (fallecida o regalada)."""

    sqlstate = "23514"  # check_violation

    def __init__(self, planta_id: UUID, estatus: str) -> None:
        super().__init__(
            f"La planta {planta_id} no está activa (estatus: {estatus})"
        )
        self.planta_id = planta_id
        self.estatus = estatus


class CorreoYaRegistrado(ErrorDeNegocio):
    """El correo ya tiene una reserva en el directorio (alta de usuario).

    El correo no se guarda en la excepción: solo existe su HMAC.
    """

    sqlstate = "23505"  # unique_violation

    def __init__(self) -> None:
        super().__init__("Ese correo ya está registrado")


class ErrorDeAutenticacion(ErrorDeNegocio):
    """No se pudo comprobar la identidad de quien llama (la API responde 401).

    Los mensajes son genéricos a propósito: no dicen si falló el correo o la
    contraseña, ni qué parte del token estaba mal, para no ayudar a un
    atacante. Nunca llevan la contraseña ni el token.
    """


class CredencialesInvalidas(ErrorDeAutenticacion):
    """Correo o contraseña incorrectos, o la cuenta está desactivada."""

    def __init__(self) -> None:
        super().__init__("Correo o contraseña incorrectos")


class TokenInvalido(ErrorDeAutenticacion):
    """El token no se puede aceptar: firma, formato o datos incorrectos."""

    def __init__(self) -> None:
        super().__init__("El token no es válido")


class TokenExpirado(TokenInvalido):
    """El token era válido, pero ya venció; hay que iniciar sesión de nuevo."""

    def __init__(self) -> None:
        ErrorDeAutenticacion.__init__(self, "El token ya venció")


class ErrorDeInfraestructura(ErrorPlantas):
    """La petición es correcta, pero un nodo o servicio no pudo atenderla.

    La API responde 503 y el cliente puede intentarlo más tarde.
    """


class NodoNoDisponible(ErrorDeInfraestructura):
    """El nodo de la región no responde (PostgreSQL o MongoDB)."""

    def __init__(self, region_id: int, servicio: str) -> None:
        super().__init__(
            f"El servicio {servicio} de la región {region_id} no responde"
        )
        self.region_id = region_id
        self.servicio = servicio


class DirectorioNoDisponible(ErrorDeInfraestructura):
    """El directorio de correos no confirmó a tiempo (D-01, sección 5).

    Afecta solo el registro y la baja de cuenta; el login sigue funcionando
    porque solo lee.
    """

    def __init__(self) -> None:
        super().__init__(
            "No se pudo confirmar el directorio de correos; intenta de nuevo"
        )


class LecturaNoGuardada(ErrorDeInfraestructura):
    """MongoDB no respondió tras los reintentos y la lectura se perdió.

    D-01 (sección 7) acepta esta pérdida: la siguiente lectura la compensa.
    """

    def __init__(self, sensor_id: UUID, intentos: int) -> None:
        super().__init__(
            f"No se guardó la lectura del sensor {sensor_id} "
            f"tras {intentos} intentos"
        )
        self.sensor_id = sensor_id
        self.intentos = intentos


class ConfiguracionInvalida(ErrorDeInfraestructura):
    """Falta una variable de entorno o su valor no es seguro.

    La API no debe arrancar así: es mejor fallar al inicio que firmar tokens
    con una llave débil. El mensaje dice qué variable, nunca su valor.
    """

    def __init__(self, variable: str, motivo: str) -> None:
        super().__init__(f"Configuración inválida en {variable}: {motivo}")
        self.variable = variable
