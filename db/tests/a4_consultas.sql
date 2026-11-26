-- =====================================================================
-- A4 · Consultas frecuentes de A1 con EXPLAIN ANALYZE
-- IA: generado y revisado (Claude) — ver docs/bitacora-ia.md
-- Lo incluye a4_explain_indices.sql dos veces: ANTES y DESPUÉS de los
-- índices. Usa las variables :region, :usuario, :planta y :correo_hmac
-- que define ese script.
-- Qué buscar en cada plan:
--   Seq Scan            = recorre la tabla completa (lento con muchos datos)
--   Index Scan / Bitmap = usa un índice
--   Sort                = tuvo que ordenar (el índice ordenado lo evita)
--   Execution Time      = tiempo real que tardó
-- =====================================================================

\echo ''
\echo '===== Q1 · Iniciar sesión: buscar el correo en el directorio ====='
EXPLAIN (ANALYZE, COSTS OFF, TIMING OFF)
SELECT region_id, usuario_id
FROM directorio_correo
WHERE correo_hmac = :'correo_hmac';

\echo ''
\echo '===== Q2 · Plantas de un usuario ====='
EXPLAIN (ANALYZE, COSTS OFF, TIMING OFF)
SELECT planta_id, apodo, estatus
FROM planta
WHERE region_id = :region AND usuario_id = :'usuario';

\echo ''
\echo '===== Q3 · Detalle de una planta con su especie ====='
EXPLAIN (ANALYZE, COSTS OFF, TIMING OFF)
SELECT p.apodo, e.nombre_comun, e.humedad_ideal_min, e.humedad_ideal_max
FROM planta p
JOIN especie e ON e.especie_id = p.especie_id
WHERE p.region_id = :region AND p.planta_id = (:'planta')::uuid;

\echo ''
\echo '===== Q4 · Historial de cuidados de una planta (más reciente primero) ====='
EXPLAIN (ANALYZE, COSTS OFF, TIMING OFF)
SELECT tipo, fecha_hora, cantidad_ml
FROM cuidado
WHERE region_id = :region AND planta_id = (:'planta')::uuid
ORDER BY fecha_hora DESC
LIMIT 20;

\echo ''
\echo '===== Q5 · Último riego de cada planta de un usuario y cuándo toca el siguiente ====='
EXPLAIN (ANALYZE, COSTS OFF, TIMING OFF)
SELECT p.apodo, ur.fecha_hora AS ultimo_riego,
       ur.fecha_hora + make_interval(days => e.frecuencia_riego_dias) AS proximo_riego
FROM planta p
JOIN especie e ON e.especie_id = p.especie_id
LEFT JOIN LATERAL (
    SELECT c.fecha_hora
    FROM cuidado c
    WHERE c.region_id = p.region_id AND c.planta_id = p.planta_id AND c.tipo = 'riego'
    ORDER BY c.fecha_hora DESC
    LIMIT 1
) ur ON true
WHERE p.region_id = :region AND p.usuario_id = :'usuario';

\echo ''
\echo '===== Q6 · Alertas pendientes de un usuario ====='
EXPLAIN (ANALYZE, COSTS OFF, TIMING OFF)
SELECT a.tipo, a.mensaje, a.fecha_generada, p.apodo
FROM alerta a
JOIN planta p ON p.region_id = a.region_id AND p.planta_id = a.planta_id
WHERE p.region_id = :region AND p.usuario_id = :'usuario'
  AND a.region_id = :region AND a.estado = 'pendiente'
ORDER BY a.fecha_generada DESC;

\echo ''
\echo '===== Q7 · Buscar especies por nombre ====='
EXPLAIN (ANALYZE, COSTS OFF, TIMING OFF)
SELECT especie_id, nombre_comun, nombre_cientifico
FROM especie
WHERE nombre_comun ILIKE '%orquí%';

\echo ''
\echo '===== Q10 · Plantas con lectura en las últimas 2 horas fuera del rango ideal ====='
EXPLAIN (ANALYZE, COSTS OFF, TIMING OFF)
SELECT p.planta_id, p.apodo, p.humedad_actual, e.humedad_ideal_min, e.humedad_ideal_max
FROM planta p
JOIN especie e ON e.especie_id = p.especie_id
WHERE p.region_id = :region
  AND p.estatus = 'activa'
  AND p.humedad_actual IS NOT NULL
  AND p.fecha_ultima_lectura >= now() - interval '2 hours'
  AND (p.humedad_actual < e.humedad_ideal_min OR p.humedad_actual > e.humedad_ideal_max);
