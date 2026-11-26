-- =====================================================================
-- A3 · Datos base: regiones y estados (opción B de fragmentación)
-- IA: generado y revisado (Claude) — ver docs/bitacora-ia.md
--
-- estado_id = clave INEGI de la entidad (01 a 32).
-- poblacion_aprox = Censo de Población y Vivienda 2020 (INEGI).
--   ¡OJO! Son cifras aproximadas: VERIFÍQUENLAS contra INEGI antes de
--   usarlas en A13 y en el registro de decisiones (D-01).
-- Opción B: Jalisco, Colima, Nayarit, Aguascalientes y San Luis Potosí
--   pasan a Norte; Puebla pasa a Sur. Resultado aproximado 36/36/28 %.
--   Si A13 cambia la decisión, solo se cambia la columna region_id aquí.
--
-- Cómo correrlo (después de 01_esquema.sql):
--   psql -U postgres -d plantas -f db/02_datos_base.sql
-- =====================================================================

\set ON_ERROR_STOP on

BEGIN;
SET search_path TO app;

INSERT INTO region (region_id, nombre) VALUES
    (1, 'Norte'),
    (2, 'Centro'),
    (3, 'Sur');

INSERT INTO estado (estado_id, nombre, region_id, poblacion_aprox) VALUES
    ( 1, 'Aguascalientes',       1,  1425607),
    ( 2, 'Baja California',      1,  3769020),
    ( 3, 'Baja California Sur',  1,   798447),
    ( 4, 'Campeche',             3,   928363),
    ( 5, 'Coahuila',             1,  3146771),
    ( 6, 'Colima',               1,   731391),
    ( 7, 'Chiapas',              3,  5543828),
    ( 8, 'Chihuahua',            1,  3741869),
    ( 9, 'Ciudad de México',     2,  9209944),
    (10, 'Durango',              1,  1832650),
    (11, 'Guanajuato',           2,  6166934),
    (12, 'Guerrero',             3,  3540685),
    (13, 'Hidalgo',              2,  3082841),
    (14, 'Jalisco',              1,  8348151),
    (15, 'Estado de México',     2, 16992418),
    (16, 'Michoacán',            2,  4748846),
    (17, 'Morelos',              2,  1971520),
    (18, 'Nayarit',              1,  1235456),
    (19, 'Nuevo León',           1,  5784442),
    (20, 'Oaxaca',               3,  4132148),
    (21, 'Puebla',               3,  6583278),
    (22, 'Querétaro',            2,  2368467),
    (23, 'Quintana Roo',         3,  1857985),
    (24, 'San Luis Potosí',      1,  2822255),
    (25, 'Sinaloa',              1,  3026943),
    (26, 'Sonora',               1,  2944840),
    (27, 'Tabasco',              3,  2402598),
    (28, 'Tamaulipas',           1,  3527735),
    (29, 'Tlaxcala',             2,  1342977),
    (30, 'Veracruz',             3,  8062579),
    (31, 'Yucatán',              3,  2320898),
    (32, 'Zacatecas',            1,  1622138);

COMMIT;

-- Comprobación: cuántos estados y qué porcentaje de población tiene cada región.
SELECT r.nombre AS region,
       count(*)  AS estados,
       sum(e.poblacion_aprox) AS poblacion,
       round(100.0 * sum(e.poblacion_aprox) / sum(sum(e.poblacion_aprox)) OVER (), 1) AS porcentaje
FROM app.estado e
JOIN app.region r USING (region_id)
GROUP BY r.region_id, r.nombre
ORDER BY r.region_id;
