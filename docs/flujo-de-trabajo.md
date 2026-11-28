# Flujo de trabajo del equipo

Resume cómo trabajamos en GitHub. Sigue los lineamientos del proyecto integrador (v5): ramas independientes, issues con criterios, commits descriptivos, pull requests revisados por otra persona y trazabilidad completa.

## Ramas
- `main` solo tiene versiones integradas y funcionales. Nadie sube directo a `main`.
- Cada tarea tiene su rama, con el prefijo del tipo de cambio, el nombre de quien trabaja y la clave de la tarea: `feature/`, `fix/`, `docs/` o `test/`. Ejemplo: `feature/andrea-b1-estructura-python`.
- Una rama por tarea. Al integrarse se puede borrar.

## Issues
- Toda tarea es un issue con título descriptivo, explicación, responsable y criterios de terminado. La clave de la tarea (por ejemplo `B1`) va al inicio del título.
- Etiquetas de tipo: `tipo:feature`, `tipo:fix`, `tipo:docs`, `tipo:test` y `tipo:error-previsto`.
- Etiquetas de estado: `estado:pendiente`, `estado:en-progreso`, `estado:en-revision`, `estado:bloqueado` y `estado:terminado`.
- Además lleva una etiqueta de componente (`datos`, `python`, `flutter`, `seguridad`, `infraestructura`, `docs`), una de fase (`fase-0` a `fase-6`) y su hito.
- Quien empieza una tarea pasa el issue a `estado:en-progreso`. Al abrir el pull request pasa a `estado:en-revision`. Al integrarse y verificarse los criterios, el issue se cierra y queda en `estado:terminado`.
- Los errores y riesgos que se detecten también se registran como issues.

## Commits
- Mensajes que describan el cambio, en español y en una línea clara.
- Commits frecuentes y de cada integrante durante todo el periodo. No se acumulan al final.
- Si hubo IA, el mensaje termina con `IA: asistido` (la IA explicó o ayudó) o `IA: generado y revisado` (la IA escribió y la persona verificó).
- Cada uso de IA que llega al repositorio se anota en `docs/bitacora-ia.md` con el hash del commit.

## Pull requests
- Se abren desde la rama hacia `main` con la plantilla llena: qué cambia, issue relacionado, cómo se verificó y uso de IA.
- El título describe el cambio. No se dejan los títulos que genera GitHub.
- El cuerpo lleva `Closes #N` si el pull request termina la tarea, o `Refs #N` si es solo una parte.
- Los revisa otra persona del equipo:

| Autor | Revisa |
|---|---|
| Alexa | Chris |
| Andrea | Alexa |
| Chris | Andrea |

- Quien revisa lee los cambios, prueba lo que pueda, comprueba los criterios del issue y aprueba o pide cambios. Una IA no puede aprobar.
- Nadie integra su propio pull request. Lo integra quien lo aprobó, con "Create a merge commit" para conservar los hashes que se citan en la bitácora de IA.
- Cuando el CI exista para el tipo de cambio, debe estar en verde antes de integrar.

## Protección de `main`
El ruleset `proteger-main` está activo, sin lista de bypass. Exige pull request con una aprobación y bloquea el borrado de la rama y el force push. Ni los administradores pueden saltárselo.

## Secretos y datos personales
- El repositorio es público: nunca se suben contraseñas, llaves, tokens, certificados ni datos personales reales. Las configuraciones van en `.env` (que está en `.gitignore`) y se documentan en `.env.example` con valores de mentira.
- Secret scanning y push protection están activos y bloquean el push si detectan una credencial.
- Si algo sensible llega a subirse, se avisa de inmediato al equipo, se revoca o cambia la credencial y se limpia el historial. No basta con borrar el archivo en un commit nuevo.
- A la IA no se le pasan datos personales reales, contraseñas, llaves ni certificados.

## Excepciones
Solo las que autoricen los profesores. El primer commit de estructura del proyecto se hizo directo a `main`, antes de activar las reglas.
