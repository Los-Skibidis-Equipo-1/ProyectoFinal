# Bitácora de uso de IA

Registro de cada vez que el equipo usó IA en el proyecto, como piden los lineamientos.
Cada integrante agrega sus propias filas, de la más antigua a la más reciente.

| Fecha · Integrante | Herramienta | Propósito | Resultado | Verificación | Commit |
|---|---|---|---|---|---|
| 2026-11-25 · Alexa | Claude | A3: revisión de A1 y A2 y generación del esquema SQL, los datos base y las pruebas | db/01_esquema.sql, db/02_datos_base.sql, db/tests/a3_pruebas_esquema.sql | Corrí los scripts en PostgreSQL 16 (Docker); las 22 pruebas de restricciones dieron OK; evidencia en docs/evidencias/a3_pruebas.txt. Falta verificar la población contra INEGI | 044f4e5 |
| 2026-11-25 · Alexa | Claude | A4: índices por consulta frecuente y EXPLAIN antes/después; corrección de tipo en directorio_correo (A3) | db/03_indices.sql, db/tests/a4_consultas.sql, db/tests/a4_explain_indices.sql | EXPLAIN ANALYZE con datos de prueba: Seq Scan pasa a Index Scan en Q2, Q4, Q5, Q6, Q7 y Q10; evidencia en docs/evidencias/a4_explain.txt | e32c630 |
| 2026-11-26 · Alexa | Claude | A1: análisis de requerimientos (entidades, consultas, escrituras, volumen y datos personales) | docs/datos/requerimientos.md | Revisé que entidades y consultas coincidan con db/01_esquema.sql y con los índices de A4; volumen marcado como supuestos; clasificación legal pendiente con Andrea | 3b454e2 |
| 2026-11-26 · Alexa | Claude | A2: diagrama entidad-relación y justificación de 3FN | docs/datos/modelo-er.md, docs/datos/modelo-er.png | El diagrama se dibuja en GitHub; atributos y llaves cruzados contra db/01_esquema.sql; la desnormalización de region_id se demuestra con las pruebas 03 y 09 de A3 | e8ae3a0 |
| 2026-11-26 · Alexa | Claude | A5: procedimiento sp_registrar_riego y funciones fn_estado_hidratacion y fn_proximo_riego | db/04_funciones.sql, db/tests/a5_pruebas_funciones.sql | Corrí las pruebas en PostgreSQL 16: 17 OK (casos correctos y 5 errores esperados con su SQLSTATE); las 22 pruebas de A3 siguen OK; evidencia en docs/evidencias/a5_pruebas.txt | pendiente |
