"""Fábricas de objetos válidos para las pruebas.

Cada función crea un objeto correcto con datos de mentira; las pruebas solo
cambian el dato que quieren probar. Así cada prueba muestra de un vistazo qué
campo es el que importa.
"""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from plantas.dominio.cuidado import Cuidado
from plantas.dominio.especie import Especie
from plantas.dominio.lecturas import LecturaAmbiente, LecturaHumedad
from plantas.dominio.planta import Planta
from plantas.dominio.usuario import Usuario

AHORA = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)
HOY = date(2026, 11, 27)
MINUTO = timedelta(minutes=1)

USUARIO_ID = UUID("11111111-1111-1111-1111-111111111111")
SENSOR_ID = UUID("22222222-2222-2222-2222-222222222222")
PLANTA_ID = UUID("33333333-3333-3333-3333-333333333333")
CUIDADO_ID = UUID("44444444-4444-4444-4444-444444444444")

# Un hash de mentira: no es una contraseña ni un hash real.
HASH_DE_MENTIRA = "h" * 64


def hacer_especie(**cambios):
    datos = {
        "nombre_comun": "Helecho",
        "nombre_cientifico": "Nephrolepis exaltata",
        "humedad_ideal_min": 40,
        "humedad_ideal_max": 70,
        "frecuencia_riego_dias": 3,
        "luz": "indirecta",
        "temp_min": 15,
        "temp_max": 28,
        "fuente": "Fuente de prueba",
    }
    datos.update(cambios)
    return Especie(**datos)


def hacer_usuario(**cambios):
    datos = {
        "region_id": 2,
        "nombre": "Ana",
        "apellidos": "López Pérez",
        "correo": "ana@example.com",
        "password_hash": HASH_DE_MENTIRA,
        "estado_id": 1,
        "usuario_id": USUARIO_ID,
    }
    datos.update(cambios)
    return Usuario(**datos)


def hacer_planta(**cambios):
    datos = {
        "region_id": 2,
        "usuario_id": USUARIO_ID,
        "especie_id": 1,
        "apodo": "Fiona",
        "tipo_espacio": "casa",
        "planta_id": PLANTA_ID,
        "ahora": AHORA,
        "hoy": HOY,
    }
    datos.update(cambios)
    return Planta(**datos)


def hacer_cuidado(**cambios):
    datos = {
        "region_id": 2,
        "planta_id": PLANTA_ID,
        "tipo": "poda",
        "fecha_hora": AHORA - MINUTO,
        "ahora": AHORA,
    }
    datos.update(cambios)
    return Cuidado(**datos)


def hacer_riego(**cambios):
    datos = {
        "region_id": 2,
        "planta_id": PLANTA_ID,
        "fecha_hora": AHORA - MINUTO,
        "ahora": AHORA,
    }
    datos.update(cambios)
    return Cuidado.riego(**datos)


def _comunes_de_lectura(cambios):
    datos = {
        "sensor_id": SENSOR_ID,
        "planta_id": PLANTA_ID,
        "region_id": 2,
        "timestamp": AHORA - MINUTO,
        "ahora": AHORA,
    }
    datos.update(cambios)
    return datos


def hacer_lectura_humedad(**cambios):
    datos = _comunes_de_lectura(cambios)
    datos.setdefault("humedad_suelo_pct", 45.5)
    return LecturaHumedad(**datos)


def hacer_lectura_ambiente(**cambios):
    datos = _comunes_de_lectura(cambios)
    datos.setdefault("temperatura_c", 22.5)
    datos.setdefault("humedad_relativa_pct", 60)
    return LecturaAmbiente(**datos)
