"""Contraseñas: nunca se guardan en claro, solo su hash con scrypt y sal.

El hash se guarda en ``usuario.password_hash`` con este formato::

    scrypt$N$r$p$sal$hash

``N``, ``r`` y ``p`` son los parámetros de costo de scrypt, y la sal y el hash
van en base64 URL-safe sin relleno. Como los parámetros viajan dentro del
hash, se pueden subir más adelante sin romper las contraseñas ya guardadas
(``necesita_rehash`` avisa cuáles se deben recalcular al iniciar sesión).

Reglas que se siguen (OWASP, Password Storage Cheat Sheet):

- Función diseñada para contraseñas y costosa en memoria: ``scrypt`` de la
  biblioteca estándar (``hashlib``), sin paquetes de terceros.
- Una sal aleatoria de 16 bytes distinta por contraseña, generada con
  ``secrets`` (dos usuarios con la misma contraseña tienen hashes distintos).
- Comparación en tiempo constante (``hmac.compare_digest``).
- La contraseña se normaliza (NFKC) para que la misma frase escrita con
  distinto teclado dé el mismo hash.

Nunca se escribe la contraseña en un mensaje de error, en un ``repr`` ni en
una bitácora.
"""

import base64
import binascii
import hashlib
import hmac
import secrets
import unicodedata

from plantas.dominio.excepciones import (
    CampoVacio,
    FormatoInvalido,
    TipoDeDatoInvalido,
    ValorFueraDeRango,
)

ALGORITMO = "scrypt"

# Costo por defecto: 2**15 iteraciones, bloques de 8 y 1 hilo (~32 MiB y
# unas decenas de milisegundos). Se puede subir con ``necesita_rehash``.
N_DEFECTO = 2**15
R_DEFECTO = 8
P_DEFECTO = 1

LARGO_SAL = 16
LARGO_HASH = 32

CONTRASENA_LARGO_MINIMO = 8
# Tope para que una contraseña enorme no sea una forma de agotar el servidor.
CONTRASENA_LARGO_MAXIMO = 128

# Topes de los parámetros que se aceptan al leer un hash guardado: si alguien
# modificara la base para pedir N = 2**40, la verificación no debe intentarlo.
_N_MINIMO, _N_MAXIMO = 2**4, 2**20
_R_MAXIMO, _P_MAXIMO = 32, 16


def validar_contrasena_nueva(contrasena: object) -> str:
    """Comprueba que una contraseña nueva sea aceptable y la devuelve.

    Pide de 8 a 128 caracteres y que no sea solo espacios. No se recortan los
    espacios de los extremos: forman parte de la contraseña. Las excepciones
    no llevan la contraseña.
    """
    if not isinstance(contrasena, str):
        raise TipoDeDatoInvalido(
            "La contraseña debe ser texto", "contraseña", None
        )
    if not contrasena.strip():
        raise CampoVacio("La contraseña no puede estar vacía", "contraseña")
    largo = len(contrasena)
    if not CONTRASENA_LARGO_MINIMO <= largo <= CONTRASENA_LARGO_MAXIMO:
        raise ValorFueraDeRango(
            f"La contraseña debe tener entre {CONTRASENA_LARGO_MINIMO} y "
            f"{CONTRASENA_LARGO_MAXIMO} caracteres",
            "contraseña",
            None,
        )
    return contrasena


def _a_bytes(contrasena: str) -> bytes:
    return unicodedata.normalize("NFKC", contrasena).encode("utf-8")


def _memoria_necesaria(n: int, r: int, p: int) -> int:
    # scrypt usa unos 128 * N * r bytes; se deja un margen.
    return 128 * n * r + 128 * r * p + 2**20


def _calcular(contrasena: str, sal: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(
        _a_bytes(contrasena),
        salt=sal,
        n=n,
        r=r,
        p=p,
        maxmem=_memoria_necesaria(n, r, p),
        dklen=LARGO_HASH,
    )


def _b64(datos: bytes) -> str:
    return base64.urlsafe_b64encode(datos).decode("ascii").rstrip("=")


def _desde_b64(texto: str) -> bytes:
    relleno = "=" * (-len(texto) % 4)
    return base64.urlsafe_b64decode(texto + relleno)


def hashear_contrasena(
    contrasena: str,
    *,
    n: int = N_DEFECTO,
    r: int = R_DEFECTO,
    p: int = P_DEFECTO,
) -> str:
    """Devuelve el hash con sal de una contraseña nueva, listo para guardar.

    Valida la contraseña antes. Los parámetros ``n``, ``r`` y ``p`` solo se
    cambian en las pruebas (para que sean rápidas) o al subir el costo.
    """
    validar_contrasena_nueva(contrasena)
    _validar_parametros(n, r, p)
    sal = secrets.token_bytes(LARGO_SAL)
    resumen = _calcular(contrasena, sal, n, r, p)
    return f"{ALGORITMO}${n}${r}${p}${_b64(sal)}${_b64(resumen)}"


def _validar_parametros(n: int, r: int, p: int) -> None:
    n_valido = (
        isinstance(n, int) and _N_MINIMO <= n <= _N_MAXIMO and n & (n - 1) == 0
    )
    r_valido = isinstance(r, int) and 1 <= r <= _R_MAXIMO
    p_valido = isinstance(p, int) and 1 <= p <= _P_MAXIMO
    if not (n_valido and r_valido and p_valido):
        raise FormatoInvalido(
            "Los parámetros de scrypt están fuera de lo permitido",
            "password_hash",
        )


def _leer_hash(hash_guardado: object) -> tuple[int, int, int, bytes, bytes]:
    """Separa un hash guardado en sus partes o lanza ``FormatoInvalido``."""
    error = FormatoInvalido(
        "El hash guardado no tiene el formato esperado", "password_hash"
    )
    if not isinstance(hash_guardado, str):
        raise error
    partes = hash_guardado.split("$")
    if len(partes) != 6 or partes[0] != ALGORITMO:
        raise error
    try:
        n, r, p = (int(x) for x in partes[1:4])
        sal = _desde_b64(partes[4])
        resumen = _desde_b64(partes[5])
    except (ValueError, binascii.Error):
        raise error from None
    if len(sal) != LARGO_SAL or len(resumen) != LARGO_HASH:
        raise error
    _validar_parametros(n, r, p)
    return n, r, p, sal, resumen


def verificar_contrasena(contrasena: object, hash_guardado: str) -> bool:
    """Dice si la contraseña corresponde al hash guardado.

    Devuelve ``False`` si la contraseña es incorrecta (o no es texto, o es
    más larga de lo permitido). Lanza ``FormatoInvalido`` si el *hash
    guardado* está dañado, porque eso es un problema del servidor y no un
    intento de acceso.
    """
    n, r, p, sal, esperado = _leer_hash(hash_guardado)
    if (
        not isinstance(contrasena, str)
        or len(contrasena) > CONTRASENA_LARGO_MAXIMO
    ):
        return False
    calculado = _calcular(contrasena, sal, n, r, p)
    return hmac.compare_digest(calculado, esperado)


def necesita_rehash(hash_guardado: str) -> bool:
    """``True`` si el hash se hizo con un costo menor al actual.

    Se usa tras un inicio de sesión correcto: si devuelve ``True`` se vuelve a
    hashear la contraseña con los parámetros nuevos y se guarda.
    """
    n, r, p, _, _ = _leer_hash(hash_guardado)
    return (n, r, p) < (N_DEFECTO, R_DEFECTO, P_DEFECTO)
