# Bitácora de uso de IA

Registro de cada vez que el equipo usó IA en el proyecto, como piden los lineamientos.
Cada integrante agrega sus propias filas, de la más antigua a la más reciente.

| Fecha · Integrante | Herramienta | Propósito | Resultado | Verificación | Commit |
|---|---|---|---|---|---|
| 2026-11-25 · Alexa | Claude | A3: revisión de A1 y A2 y generación del esquema SQL, los datos base y las pruebas | db/01_esquema.sql, db/02_datos_base.sql, db/tests/a3_pruebas_esquema.sql | Corrí los scripts en PostgreSQL 16 (Docker); las 22 pruebas de restricciones dieron OK; evidencia en docs/evidencias/a3_pruebas.txt. Falta verificar la población contra INEGI | 044f4e5 |
| 2026-11-25 · Alexa | Claude | A4: índices por consulta frecuente y EXPLAIN antes/después; corrección de tipo en directorio_correo (A3) | db/03_indices.sql, db/tests/a4_consultas.sql, db/tests/a4_explain_indices.sql | EXPLAIN ANALYZE con datos de prueba: Seq Scan pasa a Index Scan en Q2, Q4, Q5, Q6, Q7 y Q10; evidencia en docs/evidencias/a4_explain.txt | e32c630 |
