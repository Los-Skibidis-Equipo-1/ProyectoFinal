# Revisión de dependencias

Los lineamientos piden verificar que cada paquete exista y venga de su fuente oficial, porque una IA puede inventar un nombre o sugerir uno parecido (typosquatting). Este documento lista los paquetes de Python de la API (`api/requirements.txt` y `api/requirements-dev.txt`). Los paquetes de Flutter (pub.dev) y las imágenes de Docker se agregan aquí en C1 y B21, cada uno con la misma información.

Estado de la revisión (B1): las 11 versiones se instalaron sin errores y `pip-audit` no encontró vulnerabilidades conocidas (2026-11-27, Windows, Python 3.13). `ruff`, `pytest --cov` y `bandit` también pasaron. Ver «Cómo repetir la verificación».

## Paquetes de la API (`requirements.txt`)

| Paquete | Versión | Fuente oficial | Para qué se usa | Tarea |
|---|---|---|---|---|
| fastapi | 0.165.0 | [pypi.org/project/fastapi](https://pypi.org/project/fastapi/) · [github.com/fastapi/fastapi](https://github.com/fastapi/fastapi) | API REST y documentación OpenAPI | B10, B12 |
| uvicorn | 0.54.0 | [pypi.org/project/uvicorn](https://pypi.org/project/uvicorn/) · [uvicorn.dev](https://uvicorn.dev/) | Servidor que ejecuta la API | B10 |
| pymongo | 4.19.0 | [pypi.org/project/pymongo](https://pypi.org/project/pymongo/) · [github.com/mongodb/mongo-python-driver](https://github.com/mongodb/mongo-python-driver) | Lecturas de sensores en MongoDB | B14 |
| pandas | 3.0.5 | [pypi.org/project/pandas](https://pypi.org/project/pandas/) · [pandas.pydata.org](https://pandas.pydata.org/) | Limpieza y análisis de datos | B8, B16 |
| matplotlib | 3.11.2 | [pypi.org/project/matplotlib](https://pypi.org/project/matplotlib/) · [matplotlib.org](https://matplotlib.org/) | Las tres gráficas del análisis | B16 |
| PyJWT | 2.15.0 | [pypi.org/project/PyJWT](https://pypi.org/project/PyJWT/) · [github.com/jpadilla/pyjwt](https://github.com/jpadilla/pyjwt) | Tokens JWT (HS256) | B6, B11 |

Las contraseñas se protegen con `scrypt` de la biblioteca estándar (`hashlib`), así que no necesitan un paquete aparte.

## Herramientas de desarrollo (`requirements-dev.txt`)

| Paquete | Versión | Fuente oficial | Para qué se usa |
|---|---|---|---|
| pytest | 9.1.1 | [pypi.org/project/pytest](https://pypi.org/project/pytest/) · [docs.pytest.org](https://docs.pytest.org/) | Pruebas unitarias |
| pytest-cov | 7.1.0 | [pypi.org/project/pytest-cov](https://pypi.org/project/pytest-cov/) · [github.com/pytest-dev/pytest-cov](https://github.com/pytest-dev/pytest-cov) | Cobertura mínima de 60 % |
| ruff | 0.16.9 | [pypi.org/project/ruff](https://pypi.org/project/ruff/) · [github.com/astral-sh/ruff](https://github.com/astral-sh/ruff) | Estilo PEP 8 y errores comunes |
| bandit | 1.9.4 | [pypi.org/project/bandit](https://pypi.org/project/bandit/) · [github.com/PyCQA/bandit](https://github.com/PyCQA/bandit) | Análisis estático de seguridad del código |
| pip-audit | 2.10.1 | [pypi.org/project/pip-audit](https://pypi.org/project/pip-audit/) · [github.com/pypa/pip-audit](https://github.com/pypa/pip-audit) | Busca vulnerabilidades conocidas en las dependencias |

## Cómo se verificó cada paquete (2026-11-27)

- **Nombre y fuente:** se buscó cada paquete en pypi.org y se comparó el nombre exacto con el de la documentación oficial de la herramienta. Los de la tabla son los que publican los proyectos originales (PyCQA para bandit, PyPA para pip-audit, pytest-dev para pytest-cov, Astral para ruff).
- **Versión:** las 11 versiones de las tablas existen en PyPI y se instalaron con `pip install -r requirements-dev.txt` en un entorno virtual limpio (Windows, Python 3.13, pip 26.3). Antes de eso, pytest y ruff ya se habían ejecutado sobre `api/` en otro entorno. El código de uvicorn, pandas, matplotlib, PyJWT, fastapi y pymongo todavía no se usa.
- **Nombres parecidos descartados:** al buscar aparecieron `fastapi-framework`, `fastapi-advanced`, `fastapi-sdk`, `banditrs`, `flake8-bandit`, `pytest-cov-exclude` y `pytest-cov-container`. No son los paquetes que necesitamos y no se usan. En el entorno de prueba también había `httpx2`, que no es `httpx`; cuando B10 necesite el cliente de pruebas de FastAPI se instala `httpx` y se verifica aquí.
- **Vulnerabilidades (`pip-audit`):** sin hallazgos. Ver la sección siguiente.

## Resultado de `pip-audit`

Corrido el 2026-11-27 por Andrea, en `api/` con el entorno virtual activo:

| Comando | Resultado |
|---|---|
| `pip-audit -r requirements.txt` | No known vulnerabilities found |
| `pip-audit -r requirements-dev.txt` | No known vulnerabilities found |

`pip-audit` revisó también las dependencias indirectas (por ejemplo `starlette`, `pydantic`, `numpy`, `requests`). Se vuelve a correr cada vez que cambie un requirements y antes de la entrega.

## Resultado de las herramientas de calidad

Corridas el 2026-11-27 por Andrea (Windows, Python 3.13.2), desde `api/`:

| Comando | Resultado |
|---|---|
| `ruff check .` | All checks passed |
| `ruff format --check .` | 8 files already formatted |
| `pytest --cov` | 6 pruebas en OK; cobertura 100 % (mínimo exigido: 60 %) |
| `bandit -c pyproject.toml -r plantas` | No issues identified (18 líneas) |

La cobertura de 100 % todavía no dice nada: los paquetes solo tienen docstrings y no hay instrucciones que medir. Se vuelve útil desde B2, cuando haya código, y es el número que el CI va a exigir.

## Cómo repetir la verificación

Desde la carpeta `api/`, con el entorno virtual activo:

```bash
python -m venv .venv
source .venv/bin/activate        # en Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pip-audit -r requirements.txt
pip-audit -r requirements-dev.txt
pip list                         # confirma que las versiones coinciden con las de este documento
ruff check . && ruff format --check .
pytest
bandit -c pyproject.toml -r plantas
```

Si algún `pip install` falla porque una versión no existe, se corrige en el archivo de requisitos y en las tablas de arriba. `pip install` y `pip-audit` ya pasaron sin errores el 2026-11-27.

## Paquetes que faltan y se agregan con su tarea

Cada uno se verifica aquí en el mismo pull request que lo agrega, nunca antes.

| Paquete | Se agrega en | Nota |
|---|---|---|
| Controlador de PostgreSQL (psycopg) | B9 | DB-API 2.0. Elegir `psycopg` (versión 3) o `psycopg2` y anotar la decisión en `docs/registro-decisiones.md`. Los errores de A5 (`P0002` y `23514`) llegan como excepciones del controlador |
| httpx | B10 | Lo necesita el cliente de pruebas de FastAPI |
| python-multipart, email-validator u otros que pida FastAPI | B10 a B12 | Solo si la tarea los necesita |
| cryptography | B18 | Si la criptografía aplicada lo requiere |

## Dependencias indirectas

Cada paquete trae otros (por ejemplo `pydantic` y `starlette` con FastAPI, y `numpy` con pandas). `pip-audit` revisa también esas. Cuando el proyecto esté estable se puede guardar `pip freeze` como `api/requirements.lock` para reproducir la instalación exacta.
