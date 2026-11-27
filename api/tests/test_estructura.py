"""Comprueba que los paquetes de la API existen y se pueden importar."""

import importlib

import pytest

PAQUETES = [
    "plantas",
    "plantas.dominio",
    "plantas.seguridad",
    "plantas.datos",
    "plantas.analisis",
    "plantas.web",
]


@pytest.mark.parametrize("nombre", PAQUETES)
def test_el_paquete_se_puede_importar(nombre):
    modulo = importlib.import_module(nombre)
    assert modulo.__doc__, f"{nombre} debe explicar para qué sirve"
