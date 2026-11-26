\# Bitácora de uso de IA



Registro de cada vez que el equipo usó IA en el proyecto, como piden los lineamientos.

Cada integrante agrega sus propias filas, de la más antigua a la más reciente.



| Fecha · Integrante | Herramienta | Propósito | Resultado | Verificación | Commit |

|---|---|---|---|---|---|

| 2026-11-25 · Alexa | Claude | A3: revisión de A1 y A2 y generación del esquema SQL, los datos base y las pruebas | db/01\_esquema.sql, db/02\_datos\_base.sql, db/pruebas/a3\_pruebas\_esquema.sql | Corrí los 3 scripts en PostgreSQL 16 (Docker); las 22 pruebas de restricciones dieron OK; evidencia en docs/evidencias/a3\_pruebas.txt. Falta verificar la población contra INEGI | a1b2c3d |



| 2026-11-25 · Alexa | Claude | A4: índices por consulta frecuente y EXPLAIN antes/después; corrección de tipo en directorio\_correo (A3) | db/03\_indices.sql, db/pruebas/a4\_consultas.sql, db/pruebas/a4\_explain\_indices.sql | EXPLAIN ANALYZE con datos de prueba: Seq Scan pasa a Index Scan en Q2, Q4, Q5, Q6, Q7 y Q10; evidencia en docs/evidencias/a4\_explain.txt | (código del commit) |

