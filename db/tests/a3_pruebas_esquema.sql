-- =====================================================================
-- A3 · Pruebas del esquema
-- IA: generado y revisado (Claude) — ver docs/bitacora-ia.md
--
-- Inserta datos válidos y luego intenta insertar datos INVÁLIDOS.
-- Cada intento inválido debe ser RECHAZADO por una restricción.
--   "OK"    = la base rechazó el dato malo, como debe ser.
--   "FALLO" = la base aceptó un dato malo -> hay que corregir el esquema
--             (el script se detiene ahí).
-- Al final hace ROLLBACK: no deja ningún dato de prueba en la base.
--
-- Cómo correrlo (después de 01 y 02):
--   psql -U postgres -d plantas -f db/tests/a3_pruebas_esquema.sql
-- =====================================================================

\set ON_ERROR_STOP on

BEGIN;
SET search_path TO app;

-- ---------------------------------------------------------------------
-- Ayudante: ejecuta una sentencia que DEBE fallar por una restricción.
-- ---------------------------------------------------------------------
CREATE FUNCTION pg_temp.debe_fallar(prueba text, sentencia text)
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    BEGIN
        EXECUTE sentencia;
    EXCEPTION WHEN integrity_constraint_violation THEN
        RAISE NOTICE 'OK    %  (%: %)', prueba, SQLSTATE, SQLERRM;
        RETURN;
    END;
    RAISE EXCEPTION 'FALLO %  -> la base aceptó un dato inválido', prueba;
END;
$$;

-- ---------------------------------------------------------------------
-- 1. Datos válidos (deben entrar sin error)
-- ---------------------------------------------------------------------
INSERT INTO especie (nombre_comun, nombre_cientifico, humedad_ideal_min, humedad_ideal_max,
                     frecuencia_riego_dias, luz, temp_min, temp_max, cuidados, fuente)
VALUES ('Especie de prueba', 'Plantae probatio', 40, 60, 7, 'indirecta', 15, 28,
        'Solo para pruebas', 'Dato inventado para pruebas');

-- Usuario de Centro (región 2) en Ciudad de México (estado 9).
INSERT INTO usuario (region_id, usuario_id, nombre, apellidos, correo, password_hash, estado_id)
VALUES (2, '11111111-1111-1111-1111-111111111111', 'Usuaria', 'De Prueba',
        'prueba@ejemplo.com', repeat('x', 64), 9);

INSERT INTO planta (region_id, planta_id, usuario_id, especie_id, apodo, tipo_espacio)
SELECT 2, '22222222-2222-2222-2222-222222222222', '11111111-1111-1111-1111-111111111111',
       especie_id, 'Potus de la sala', 'departamento'
FROM especie WHERE nombre_cientifico = 'Plantae probatio';

INSERT INTO sensor (region_id, planta_id, tipo, es_simulado)
VALUES (2, '22222222-2222-2222-2222-222222222222', 'humedad', true);

INSERT INTO cuidado (region_id, planta_id, tipo, cantidad_ml)
VALUES (2, '22222222-2222-2222-2222-222222222222', 'riego', 250);

INSERT INTO alerta (region_id, planta_id, tipo, mensaje)
VALUES (2, '22222222-2222-2222-2222-222222222222', 'humedad_baja', 'La humedad bajó del mínimo');

INSERT INTO directorio_correo (correo_hmac, region_id, usuario_id)
VALUES (repeat('a', 64), 2, '11111111-1111-1111-1111-111111111111');

\echo '--- Datos válidos insertados. Ahora los inválidos: ---'
\pset tuples_only on

-- ---------------------------------------------------------------------
-- 2. Datos inválidos (cada uno debe ser rechazado)
-- ---------------------------------------------------------------------
SELECT pg_temp.debe_fallar('01 región fuera de 1..3',
  $q$INSERT INTO region VALUES (4, 'Otra')$q$);

SELECT pg_temp.debe_fallar('02 usuario en región sin partición',
  $q$INSERT INTO usuario (region_id, nombre, apellidos, correo, password_hash, estado_id)
     VALUES (5, 'A', 'B', 'c@d.com', repeat('x', 64), 9)$q$);

SELECT pg_temp.debe_fallar('03 usuario en Norte con estado del Centro (CDMX)',
  $q$INSERT INTO usuario (region_id, nombre, apellidos, correo, password_hash, estado_id)
     VALUES (1, 'A', 'B', 'otro@ejemplo.com', repeat('x', 64), 9)$q$);

SELECT pg_temp.debe_fallar('04 correo con mayúsculas',
  $q$INSERT INTO usuario (region_id, nombre, apellidos, correo, password_hash, estado_id)
     VALUES (2, 'A', 'B', 'Mayus@Ejemplo.com', repeat('x', 64), 9)$q$);

SELECT pg_temp.debe_fallar('05 correo sin formato válido',
  $q$INSERT INTO usuario (region_id, nombre, apellidos, correo, password_hash, estado_id)
     VALUES (2, 'A', 'B', 'sin-arroba', repeat('x', 64), 9)$q$);

SELECT pg_temp.debe_fallar('06 correo repetido en la misma región',
  $q$INSERT INTO usuario (region_id, nombre, apellidos, correo, password_hash, estado_id)
     VALUES (2, 'A', 'B', 'prueba@ejemplo.com', repeat('x', 64), 9)$q$);

SELECT pg_temp.debe_fallar('07 rol que no existe',
  $q$INSERT INTO usuario (region_id, nombre, apellidos, correo, password_hash, estado_id, rol)
     VALUES (2, 'A', 'B', 'rol@ejemplo.com', repeat('x', 64), 9, 'root')$q$);

SELECT pg_temp.debe_fallar('08 password_hash demasiado corto',
  $q$INSERT INTO usuario (region_id, nombre, apellidos, correo, password_hash, estado_id)
     VALUES (2, 'A', 'B', 'corto@ejemplo.com', '1234', 9)$q$);

SELECT pg_temp.debe_fallar('09 planta en Norte de una usuaria del Centro',
  $q$INSERT INTO planta (region_id, usuario_id, especie_id, apodo, tipo_espacio)
     SELECT 1, '11111111-1111-1111-1111-111111111111', especie_id, 'X', 'casa'
     FROM especie LIMIT 1$q$);

SELECT pg_temp.debe_fallar('10 planta con tipo_espacio inválido',
  $q$INSERT INTO planta (region_id, usuario_id, especie_id, apodo, tipo_espacio)
     SELECT 2, '11111111-1111-1111-1111-111111111111', especie_id, 'X', 'jardin'
     FROM especie LIMIT 1$q$);

SELECT pg_temp.debe_fallar('11 planta con especie que no existe',
  $q$INSERT INTO planta (region_id, usuario_id, especie_id, apodo, tipo_espacio)
     VALUES (2, '11111111-1111-1111-1111-111111111111', 999999, 'X', 'casa')$q$);

SELECT pg_temp.debe_fallar('12 planta con humedad pero sin fecha de lectura',
  $q$INSERT INTO planta (region_id, usuario_id, especie_id, apodo, tipo_espacio, humedad_actual)
     SELECT 2, '11111111-1111-1111-1111-111111111111', especie_id, 'X', 'casa', 50
     FROM especie LIMIT 1$q$);

SELECT pg_temp.debe_fallar('13 especie con humedad mínima mayor que la máxima',
  $q$INSERT INTO especie (nombre_comun, nombre_cientifico, humedad_ideal_min, humedad_ideal_max,
                          frecuencia_riego_dias, luz, temp_min, temp_max, fuente)
     VALUES ('X', 'X x', 70, 30, 7, 'directa', 10, 30, 'fuente')$q$);

SELECT pg_temp.debe_fallar('14 especie sin fuente (cadena vacía)',
  $q$INSERT INTO especie (nombre_comun, nombre_cientifico, humedad_ideal_min, humedad_ideal_max,
                          frecuencia_riego_dias, luz, temp_min, temp_max, fuente)
     VALUES ('X', 'X y', 30, 70, 7, 'directa', 10, 30, '   ')$q$);

SELECT pg_temp.debe_fallar('15 especie con nombre científico repetido',
  $q$INSERT INTO especie (nombre_comun, nombre_cientifico, humedad_ideal_min, humedad_ideal_max,
                          frecuencia_riego_dias, luz, temp_min, temp_max, fuente)
     VALUES ('X', 'Plantae probatio', 30, 70, 7, 'directa', 10, 30, 'fuente')$q$);

SELECT pg_temp.debe_fallar('16 poda con cantidad_ml',
  $q$INSERT INTO cuidado (region_id, planta_id, tipo, cantidad_ml)
     VALUES (2, '22222222-2222-2222-2222-222222222222', 'poda', 100)$q$);

SELECT pg_temp.debe_fallar('17 riego con cantidad negativa',
  $q$INSERT INTO cuidado (region_id, planta_id, tipo, cantidad_ml)
     VALUES (2, '22222222-2222-2222-2222-222222222222', 'riego', -5)$q$);

SELECT pg_temp.debe_fallar('18 sensor real sin identificador de dispositivo',
  $q$INSERT INTO sensor (region_id, planta_id, tipo, es_simulado)
     VALUES (2, '22222222-2222-2222-2222-222222222222', 'ambiente', false)$q$);

SELECT pg_temp.debe_fallar('19 alerta atendida sin fecha de atención',
  $q$INSERT INTO alerta (region_id, planta_id, tipo, mensaje, estado)
     VALUES (2, '22222222-2222-2222-2222-222222222222', 'temperatura', 'X', 'atendida')$q$);

SELECT pg_temp.debe_fallar('20 directorio con hash que no es hexadecimal',
  $q$INSERT INTO directorio_correo VALUES ('no-es-un-hash', 2, gen_random_uuid())$q$);

SELECT pg_temp.debe_fallar('21 borrar una especie que tiene plantas',
  $q$DELETE FROM especie WHERE nombre_cientifico = 'Plantae probatio'$q$);

SELECT pg_temp.debe_fallar('22 auditoría de INSERT con datos anteriores',
  $q$INSERT INTO auditoria (tabla, operacion, registro_id, datos_anteriores, datos_nuevos)
     VALUES ('planta', 'INSERT', 'x', '{}'::jsonb, '{}'::jsonb)$q$);

-- ---------------------------------------------------------------------
-- 3. Comportamientos que SÍ deben ocurrir
-- ---------------------------------------------------------------------
\pset tuples_only off
\echo '--- Las filas quedaron en la partición de su región: ---'
SELECT tableoid::regclass AS particion, count(*) FROM usuario GROUP BY 1;
SELECT tableoid::regclass AS particion, count(*) FROM planta  GROUP BY 1;

\echo '--- Borrar la usuaria borra en cascada sus plantas, sensores, cuidados y alertas: ---'
DELETE FROM usuario WHERE usuario_id = '11111111-1111-1111-1111-111111111111';
SELECT (SELECT count(*) FROM planta)  AS plantas,
       (SELECT count(*) FROM sensor)  AS sensores,
       (SELECT count(*) FROM cuidado) AS cuidados,
       (SELECT count(*) FROM alerta)  AS alertas;

ROLLBACK;

\echo 'Pruebas terminadas: si todas dicen OK, el esquema cumple A3.'
