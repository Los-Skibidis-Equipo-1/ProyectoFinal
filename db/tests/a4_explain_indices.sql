-- =====================================================================
-- A4 · EXPLAIN antes y después de los índices
-- IA: generado y revisado (Claude) — ver docs/bitacora-ia.md
--
-- Qué hace:
--   1. Carga datos de PRUEBA (no son los 100 mil de A13): 5 000 especies,
--      6 000 usuarios, 18 000 plantas, 180 000 cuidados y 54 000 alertas.
--      Sin datos, PostgreSQL siempre recorre la tabla y el EXPLAIN no
--      demuestra nada.
--   2. Quita los índices de A4 y corre las consultas  -> ANTES
--   3. Crea los índices (incluye ../03_indices.sql)   -> DESPUÉS
--   4. ROLLBACK: no deja ni los datos de prueba ni los cambios.
--      Los índices reales se quedan creados porque 03_indices.sql
--      ya se había corrido antes por separado.
--
-- Cómo correrlo (después de 01, 02 y 03):
--   psql -U postgres -d plantas -f db/pruebas/a4_explain_indices.sql
-- A18 repite estas mismas consultas con los 100 000 registros de A13.
-- =====================================================================

\set ON_ERROR_STOP on
\pset pager off

BEGIN;
SET search_path TO app, public;
SELECT setseed(0.42);   -- mismos datos "aleatorios" cada vez que se corre

-- ---------------------------------------------------------------------
-- 1. Datos de prueba
-- ---------------------------------------------------------------------
\echo 'Cargando datos de prueba (tarda unos segundos)...'

-- 10 nombres reales y 4 990 nombres aleatorios.
INSERT INTO especie (nombre_comun, nombre_cientifico, humedad_ideal_min, humedad_ideal_max,
                     frecuencia_riego_dias, luz, temp_min, temp_max, fuente)
SELECT CASE WHEN i <= 10
            THEN (ARRAY['Potus','Helecho','Sábila','Monstera','Cactus',
                        'Lavanda','Orquídea','Suculenta','Ficus','Bambú'])[i]
            ELSE 'Prueba ' || substr(md5(i::text), 1, 10) END,
       'Genus prueba ' || i,
       30, 60, 1 + (i % 14), 'indirecta', 15, 30,
       'Dato de prueba A4'
FROM generate_series(1, 5000) AS i;

-- 6 000 usuarios repartidos en las 3 regiones, cada uno en un estado de su región.
WITH estados AS (
    SELECT region_id, array_agg(estado_id ORDER BY estado_id) AS ids
    FROM estado GROUP BY region_id
)
INSERT INTO usuario (region_id, usuario_id, nombre, apellidos, correo, password_hash, estado_id)
SELECT r, md5('u' || i)::uuid, 'Nombre' || i, 'Apellido' || i,
       'u' || i || '@ejemplo.com', repeat('x', 64),
       e.ids[1 + (i % array_length(e.ids, 1))]
FROM generate_series(1, 6000) AS i
CROSS JOIN LATERAL (SELECT 1 + (i % 3) AS r) AS rr
JOIN estados e ON e.region_id = rr.r;

INSERT INTO directorio_correo (correo_hmac, region_id, usuario_id)
SELECT md5('u' || usuario_id_txt) || md5('u' || usuario_id_txt), region_id, usuario_id
FROM (SELECT region_id, usuario_id,
             substr(correo, 2, position('@' IN correo) - 2) AS usuario_id_txt
      FROM usuario) AS u;

-- 3 plantas por usuario; humedad actual y última lectura en las últimas 72 h.
INSERT INTO planta (region_id, planta_id, usuario_id, especie_id, apodo, tipo_espacio,
                    estatus, humedad_actual, fecha_ultima_lectura)
SELECT u.region_id,
       md5('p' || substr(u.correo, 2, position('@' IN u.correo) - 2) || '-' || j)::uuid,
       u.usuario_id,
       m.min_id + floor(random() * 5000)::int,  -- ids reales (la secuencia puede no empezar en 1)
       'Planta ' || j,
       (ARRAY['casa','departamento','oficina','patio'])[1 + floor(random() * 4)::int],
       CASE WHEN random() < 0.9 THEN 'activa' ELSE 'fallecida' END,
       round((random() * 100)::numeric, 2),
       now() - random() * interval '72 hours'
FROM usuario u
CROSS JOIN generate_series(1, 3) AS j
CROSS JOIN (SELECT min(especie_id) AS min_id FROM especie) AS m;

-- 10 cuidados por planta en los últimos 100 días (60 % riegos).
-- random() va en la lista del SELECT interno para que cada fila tenga su
-- propio número aleatorio.
INSERT INTO cuidado (region_id, planta_id, tipo, fecha_hora, cantidad_ml)
SELECT region_id, planta_id, tipo, fecha_hora,
       CASE WHEN tipo = 'riego' THEN 100 + floor(r3 * 400)::int END
FROM (
    SELECT region_id, planta_id, fecha_hora, r3,
           CASE WHEN r1 < 0.6 THEN 'riego'
                ELSE (ARRAY['fertilizado','poda','trasplante','otro'])[1 + floor(r2 * 4)::int]
           END AS tipo
    FROM (
        SELECT p.region_id, p.planta_id,
               now() - random() * interval '100 days' AS fecha_hora,
               random() AS r1, random() AS r2, random() AS r3
        FROM planta p
        CROSS JOIN generate_series(1, 10) AS k
    ) AS base
) AS t;

-- 3 alertas por planta: 20 % pendientes, el resto atendidas.
INSERT INTO alerta (region_id, planta_id, tipo, mensaje, fecha_generada, estado, fecha_atendida)
SELECT region_id, planta_id, 'humedad_baja', 'Alerta de prueba', fecha,
       CASE WHEN r < 0.2 THEN 'pendiente' ELSE 'atendida' END,
       CASE WHEN r < 0.2 THEN NULL ELSE fecha + interval '3 hours' END
FROM (
    SELECT p.region_id, p.planta_id,
           now() - random() * interval '60 days' AS fecha,
           random() AS r
    FROM planta p
    CROSS JOIN generate_series(1, 3) AS k
) AS base;

SELECT 'especie' AS tabla, count(*) FROM especie
UNION ALL SELECT 'usuario', count(*) FROM usuario
UNION ALL SELECT 'planta',  count(*) FROM planta
UNION ALL SELECT 'cuidado', count(*) FROM cuidado
UNION ALL SELECT 'alerta',  count(*) FROM alerta;

-- Usuaria de prueba: la primera de la región 1 (Norte) que tenga alertas
-- pendientes, para que Q6 sí devuelva filas. Q3 y Q4 usan su primera planta.
\set region 1
SELECT p.usuario_id AS usuario, min(p.planta_id::text) AS planta
FROM planta p
JOIN alerta a ON a.region_id = p.region_id AND a.planta_id = p.planta_id
WHERE p.region_id = 1 AND a.estado = 'pendiente'
GROUP BY p.usuario_id
ORDER BY p.usuario_id
LIMIT 1 \gset
SELECT correo_hmac AS correo_hmac FROM directorio_correo WHERE usuario_id = :'usuario' \gset

-- ---------------------------------------------------------------------
-- 2. ANTES: sin los índices de A4
-- ---------------------------------------------------------------------
DROP INDEX IF EXISTS idx_planta_usuario, idx_cuidado_planta_fecha, idx_cuidado_riego,
                     idx_alerta_pendiente, idx_especie_nombre_trgm, idx_planta_lectura_activa,
                     idx_planta_especie, idx_sensor_planta, idx_alerta_planta;
ANALYZE;

\echo ''
\echo '#####################################################################'
\echo '#  ANTES DE LOS ÍNDICES                                             #'
\echo '#####################################################################'
\ir a4_consultas.sql

-- ---------------------------------------------------------------------
-- 3. DESPUÉS: con los índices de A4
-- ---------------------------------------------------------------------
\ir ../03_indices.sql
ANALYZE;

\echo ''
\echo '#####################################################################'
\echo '#  DESPUÉS DE LOS ÍNDICES                                           #'
\echo '#####################################################################'
\ir a4_consultas.sql

ROLLBACK;

\echo ''
\echo 'Listo. Compara cada consulta: Seq Scan -> Index Scan y el Execution Time.'
