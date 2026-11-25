# Sistema casero de registro y cuidado de plantas con sensores

Una aplicación para llevar el cuidado de tus plantas sin que se te olvide nada. Registras tus plantas, anotas cuándo las riegas o las fertilizas, consultas qué necesita cada especie y recibes recordatorios y alertas. Con sensores de humedad y de ambiente, el sistema también avisa cuando una planta necesita agua. Está pensada para casas, departamentos, oficinas y patios de todo México.

Proyecto Integrador del Equipo 01 «Los Skibidis», Ingeniería en Sistemas Computacionales, UAA, 7.º semestre. Reúne cuatro materias: Ingeniería de Datos I, Seguridad en Sistemas de Cómputo, Programación de Dispositivos Móviles y Programación en Python.

## Equipo

|~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~|
| Integrante | GitHub | Componente que defiende |
|~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~|


| Alexa Yalee Sánchez Tejeda | [alexayalee](https://github.com/alexayalee) | Datos: esquema, fragmentación y réplica, MongoDB, datos sintéticos |

| Andrea Guadalupe Pérez Jiménez | [AndreaPrz28](https://github.com/AndreaPrz28) | Python y Seguridad (aplicación): API, análisis con pandas, roles, criptografía |

| Christopher Orlando Jáuregui Rangel | [chrisorJR09](https://github.com/chrisorJR09) | Flutter e infraestructura segura: app, VPN, SSH, firewall, detección de intrusos, integración continua |

|~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~|

## Tecnologías

- **Bases de datos:** PostgreSQL (datos de usuarios, plantas y cuidados) y MongoDB (lecturas de sensores).
- **API:** Python con FastAPI.
- **Aplicación:** Flutter, con una misma base de código para Android, web y Windows.
- **Infraestructura:** Docker y Docker Compose, con una VPN WireGuard entre los nodos.
- **Control de versiones:** Git y GitHub.

## Arquitectura general

El sistema corre en tres nodos, uno por computadora y todos en contenedores: Norte, Centro y Sur. Los datos personales de los usuarios y las lecturas de los sensores se reparten entre los nodos según la región del usuario. El catálogo de especies es igual en todos, porque cualquier nodo debe poder consultarlo. Los nodos se comunican por una VPN cifrada, y cada región se replica en otro nodo para que el sistema siga funcionando si uno se cae. La distribución exacta de los estados entre las regiones se está definiendo.

## Estructura del repositorio

| Carpeta | Contenido | Responsable |
|---|---|---|
| `db/` | Esquema SQL, procedimientos, triggers, roles y pruebas | Alexa |
| `api/` | API en Python, lógica del dominio y pruebas | Andrea |
| `app/` | Aplicación Flutter | Chris |
| `infra/` | VPN, SSH, firewall, contenedores y detección de intrusos | Chris |
| `docs/` | Documentación, bitácora de IA, registro de decisiones y evidencias | Todos |
| `.github/` | Integración continua y plantilla de pull requests | Chris |

## Cómo trabajamos

- Cada tarea es un issue con responsable, criterios de terminado y etiquetas, agrupadas por fases en los hitos del repositorio.
- Una rama por tarea, con nombre descriptivo: `feature/`, `fix/`, `docs/` o `test/`.
- Todo cambio entra por un pull request. Lo revisa otro integrante: Alexa revisa a Andrea, Andrea revisa a Chris y Chris revisa a Alexa.
- Si se usó IA, el commit termina con `IA: asistido` o `IA: generado y revisado`, y se anota en `docs/bitacora-ia.md`.
- No se suben contraseñas, llaves ni certificados. Las variables de configuración van en un archivo `.env` local, y `.env.example` muestra cuáles son.

## Estado

En desarrollo.