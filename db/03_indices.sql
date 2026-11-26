-- =====================================================================
-- A4 · Índices — uno por cada consulta frecuente de A1
-- PostgreSQL 16
-- Responsable: Alexa Yalee Sánchez Tejeda
-- IA: generado y revisado (Claude) — ver docs/bitacora-ia.md
--
-- Notas importantes:
--  * Un índice creado sobre una tabla particionada se crea solo en cada
--    partición (usuario_r1, usuario_r2, usuario_r3, etc.).
--  * Todos los índices de tablas fragmentadas empiezan con region_id,
--    igual que las consultas, para que PostgreSQL entre solo a la
--    partición de esa región.
--  * Q1 y Q3 no necesitan índice nuevo: ya los cubren los índices que
--    PostgreSQL crea solo para las PRIMARY KEY y los UNIQUE de A3.
--  * Q8 y Q9 son de MongoDB: sus índices van en A15.
--  * Este archivo NO abre ni cierra transacción, para que el script de
--    pruebas pueda incluirlo dentro de la suya.
--
-- Cómo correrlo (después de 01 y 02):
--   psql -U postgres -d plantas -f db/03_indices.sql
-- =====================================================================

\set ON_ERROR_STOP on
SET search_path TO app, public;

-- Extensión para búsquedas de texto con ILIKE '%texto%' (Q7).
-- Viene incluida en la imagen oficial postgres:16.
CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;

-- ---------------------------------------------------------------------
-- Q2 · Listar las plantas de un usuario
--   WHERE region_id = ? AND usuario_id = ?
-- También acelera el borrado en cascada de un usuario.
-- ---------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_planta_usuario
    ON planta (region_id, usuario_id);

-- ---------------------------------------------------------------------
-- Q4 · Historial de cuidados de una planta, del más reciente al más antiguo
--   WHERE region_id = ? AND planta_id = ? ORDER BY fecha_hora DESC
-- El índice ya viene ordenado: PostgreSQL no tiene que ordenar nada.
-- ---------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_cuidado_planta_fecha
    ON cuidado (region_id, planta_id, fecha_hora DESC);

-- ---------------------------------------------------------------------
-- Q5 · Último riego de cada planta de un usuario (recordatorios)
--   ... WHERE tipo = 'riego' ORDER BY fecha_hora DESC LIMIT 1
-- Índice PARCIAL: solo guarda las filas de riego, así es más chico
-- que el de Q4 y llega directo al último riego.
-- ---------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_cuidado_riego
    ON cuidado (region_id, planta_id, fecha_hora DESC)
    WHERE tipo = 'riego';

-- ---------------------------------------------------------------------
-- Q6 · Alertas pendientes de un usuario (vía sus plantas)
--   WHERE estado = 'pendiente' ORDER BY fecha_generada DESC
-- Índice PARCIAL: las alertas atendidas (la mayoría con el tiempo)
-- no ocupan espacio en él.
-- ---------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_alerta_pendiente
    ON alerta (region_id, planta_id, fecha_generada DESC)
    WHERE estado = 'pendiente';

-- ---------------------------------------------------------------------
-- Q7 · Buscar especies por nombre (ILIKE '%texto%')
-- Un índice normal (B-tree) no sirve cuando el texto empieza con '%'.
-- El índice GIN de trigramas sí, y además ignora mayúsculas.
-- ---------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_especie_nombre_trgm
    ON especie USING gin (nombre_comun gin_trgm_ops);

-- ---------------------------------------------------------------------
-- Q10 · Plantas activas de una región cuya humedad actual está fuera
--       del rango ideal de su especie (y que tienen lectura reciente)
--   WHERE region_id = ? AND estatus = 'activa'
--     AND fecha_ultima_lectura >= now() - interval '1 day'
-- Índice PARCIAL: solo plantas activas con lectura.
-- ---------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_planta_lectura_activa
    ON planta (region_id, fecha_ultima_lectura DESC)
    WHERE estatus = 'activa' AND humedad_actual IS NOT NULL;

-- ---------------------------------------------------------------------
-- Índices de apoyo a llaves foráneas (no son de una consulta de A1,
-- pero sin ellos cada borrado en cascada recorre la tabla completa).
-- ---------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_planta_especie ON planta (especie_id);
CREATE INDEX IF NOT EXISTS idx_sensor_planta  ON sensor (region_id, planta_id);
CREATE INDEX IF NOT EXISTS idx_alerta_planta  ON alerta (region_id, planta_id);

\echo 'Índices de A4 creados correctamente.'
