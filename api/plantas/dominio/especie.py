"""Especie de planta: la ficha de cuidados que usan todas las plantas."""

from plantas.dominio.catalogos import (
    HUMEDAD_MAX,
    HUMEDAD_MIN,
    NIVELES_LUZ,
    TEMPERATURA_MAX,
    TEMPERATURA_MIN,
)
from plantas.dominio.validaciones import (
    validar_entero_positivo,
    validar_frecuencia_riego_dias,
    validar_humedad,
    validar_opcion,
    validar_par_ordenado,
    validar_texto_no_vacio,
    validar_texto_opcional,
)


class Especie:
    """Una especie con su rango ideal de humedad, temperatura y riego.

    Los rangos se cambian de a pares (``cambiar_rango_humedad`` y
    ``cambiar_rango_temperatura``) para que el mínimo siempre sea menor que
    el máximo. El nombre científico identifica a la especie y no cambia.
    """

    def __init__(
        self,
        *,
        nombre_comun: str,
        nombre_cientifico: str,
        humedad_ideal_min: float,
        humedad_ideal_max: float,
        frecuencia_riego_dias: int,
        luz: str,
        temp_min: float,
        temp_max: float,
        fuente: str,
        cuidados: str | None = None,
        especie_id: int | None = None,
    ) -> None:
        self._especie_id = (
            None
            if especie_id is None
            else validar_entero_positivo(especie_id, "especie_id")
        )
        self._nombre_cientifico = validar_texto_no_vacio(
            nombre_cientifico, "nombre científico", 120
        )
        self.nombre_comun = nombre_comun
        self.frecuencia_riego_dias = frecuencia_riego_dias
        self.luz = luz
        self.fuente = fuente
        self.cuidados = cuidados
        self._humedad_ideal = (0.0, 0.0)
        self._temperatura = (0.0, 0.0)
        self.cambiar_rango_humedad(humedad_ideal_min, humedad_ideal_max)
        self.cambiar_rango_temperatura(temp_min, temp_max)

    # --- datos que no cambian ---------------------------------------------

    @property
    def especie_id(self) -> int | None:
        """Lo asigna la base al guardar; es ``None`` si aún no se guarda."""
        return self._especie_id

    @property
    def nombre_cientifico(self) -> str:
        return self._nombre_cientifico

    # --- datos que se pueden cambiar, siempre validados -------------------

    @property
    def nombre_comun(self) -> str:
        return self._nombre_comun

    @nombre_comun.setter
    def nombre_comun(self, valor: str) -> None:
        self._nombre_comun = validar_texto_no_vacio(valor, "nombre común", 80)

    @property
    def frecuencia_riego_dias(self) -> int:
        return self._frecuencia_riego_dias

    @frecuencia_riego_dias.setter
    def frecuencia_riego_dias(self, valor: int) -> None:
        self._frecuencia_riego_dias = validar_frecuencia_riego_dias(valor)

    @property
    def luz(self) -> str:
        return self._luz

    @luz.setter
    def luz(self, valor: str) -> None:
        self._luz = validar_opcion(valor, "luz", NIVELES_LUZ)

    @property
    def fuente(self) -> str:
        return self._fuente

    @fuente.setter
    def fuente(self, valor: str) -> None:
        self._fuente = validar_texto_no_vacio(valor, "fuente")

    @property
    def cuidados(self) -> str | None:
        return self._cuidados

    @cuidados.setter
    def cuidados(self, valor: str | None) -> None:
        self._cuidados = validar_texto_opcional(valor, "cuidados", 5000)

    # --- rangos: se cambian de a pares ------------------------------------

    @property
    def humedad_ideal_min(self) -> float:
        return self._humedad_ideal[0]

    @property
    def humedad_ideal_max(self) -> float:
        return self._humedad_ideal[1]

    @property
    def temp_min(self) -> float:
        return self._temperatura[0]

    @property
    def temp_max(self) -> float:
        return self._temperatura[1]

    def cambiar_rango_humedad(self, minimo: float, maximo: float) -> None:
        """Humedad ideal en porcentaje, de 0 a 100, con mínimo < máximo."""
        self._humedad_ideal = validar_par_ordenado(
            minimo, maximo, "humedad ideal", HUMEDAD_MIN, HUMEDAD_MAX
        )

    def cambiar_rango_temperatura(self, minimo: float, maximo: float) -> None:
        """Temperatura en °C, de -20 a 60, con mínimo < máximo."""
        self._temperatura = validar_par_ordenado(
            minimo, maximo, "temperatura", TEMPERATURA_MIN, TEMPERATURA_MAX
        )

    # --- comportamiento ---------------------------------------------------

    def humedad_en_rango(self, humedad: float) -> bool:
        """``True`` si la humedad está en el rango ideal (incluye bordes)."""
        valor = validar_humedad(humedad)
        return self.humedad_ideal_min <= valor <= self.humedad_ideal_max

    # --- identidad --------------------------------------------------------

    def __eq__(self, otra: object) -> bool:
        if not isinstance(otra, Especie):
            return NotImplemented
        return self.nombre_cientifico.lower() == otra.nombre_cientifico.lower()

    def __hash__(self) -> int:
        return hash(self.nombre_cientifico.lower())

    def __repr__(self) -> str:
        return f"Especie({self.nombre_cientifico!r})"
