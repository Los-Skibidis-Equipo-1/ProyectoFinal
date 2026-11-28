-- =====================================================================
-- A11 · Pruebas de replicación entre los 3 nodos
-- IA: generado y revisado (Claude) — ver docs/bitacora-ia.md
--
-- Se corre UNA vez, desde cualquier nodo; el script se conecta a los 3
-- (\connect) y comprueba que "un dato escrito en un nodo aparece en su
-- réplica" (criterio de A11), además de RLS y el directorio síncrono.
--   psql -U postgres -d plantas -v escritor=norte \
--        -v host_norte=pg-norte -v host_centro=pg-centro -v host_sur=pg-sur \
--        -f db/tests/a11_pruebas_replicacion.sql
-- Opcionales: -v port_norte=5432 (y centro, sur). La contraseña de
-- postgres se toma de PGPASSWORD.
--
-- Anillo (D-01): Norte (región 1) -> copia en Centro;
--                Centro (región 2) -> copia en Sur; Sur (región 3) -> copia en Norte.
-- Al final borra todo lo que insertó y comprueba que el borrado también
-- se replica.
-- =====================================================================

\set ON_ERROR_STOP on
\pset tuples_only on

\if :{?escritor}
\else
    \echo 'ERROR: falta -v escritor=<norte|centro|sur>'
    \quit
\endif
\if :{?host_norte}
\else
    \echo 'ERROR: faltan -v host_norte=... -v host_centro=... -v host_sur=...'
    \quit
\endif
\if :{?port_norte}
\else
    \set port_norte 5432
\endif
\if :{?port_centro}
\else
    \set port_centro 5432
\endif
\if :{?port_sur}
\else
    \set port_sur 5432
\endif

SELECT format('host=%s port=%s dbname=plantas user=postgres', :'host_norte',  :'port_norte')  AS c_norte,
       format('host=%s port=%s dbname=plantas user=postgres', :'host_centro', :'port_centro') AS c_centro,
       format('host=%s port=%s dbname=plantas user=postgres', :'host_sur',    :'port_sur')    AS c_sur \gset
SELECT CASE :'escritor' WHEN 'norte' THEN :'c_norte' WHEN 'centro' THEN :'c_centro' ELSE :'c_sur' END AS c_escritor,
       (:'escritor' = 'centro') AS centro_es_escritor \gset

-- Identificadores de prueba
\set u1 '''a1100000-0000-0000-0000-000000000001'''
\set u2 '''a1100000-0000-0000-0000-000000000002'''
\set p1 '''a1100000-0000-0000-0000-0000000000f1'''

-- =====================================================================
\echo '=== 0. Esperar a que termine la copia inicial en los 3 nodos ==='
-- =====================================================================
\connect :c_norte
\ir _ayudantes.sql
SELECT pg_temp.espera('00a Norte terminó la copia inicial de sus suscripciones',
       $q$SELECT NOT EXISTS (SELECT 1 FROM pg_subscription_rel WHERE srsubstate <> 'r')$q$, 120);
\connect :c_centro
\ir _ayudantes.sql
SELECT pg_temp.espera('00b Centro terminó la copia inicial de sus suscripciones',
       $q$SELECT NOT EXISTS (SELECT 1 FROM pg_subscription_rel WHERE srsubstate <> 'r')$q$, 120);
\connect :c_sur
\ir _ayudantes.sql
SELECT pg_temp.espera('00c Sur terminó la copia inicial de sus suscripciones',
       $q$SELECT NOT EXISTS (SELECT 1 FROM pg_subscription_rel WHERE srsubstate <> 'r')$q$, 120);

-- =====================================================================
\echo '=== 1. Escritor de las globales (' :escritor ') ==='
-- =====================================================================
\connect :c_escritor
\ir _ayudantes.sql
SET search_path TO app;

SELECT pg_temp.verifica('01 el directorio es síncrono: synchronous_standby_names = ANY 1 (...)',
       current_setting('synchronous_standby_names') LIKE 'ANY 1 (sub_glob_%');
SELECT pg_temp.verifica('02 por defecto el escritor confirma sin esperar (synchronous_commit = local)',
       current_setting('synchronous_commit') = 'local');
SELECT pg_temp.espera('03 los 2 suscriptores de las globales están conectados en modo quórum',
       $q$SELECT count(*) = 2 FROM pg_stat_replication
          WHERE application_name LIKE 'sub_glob_%' AND sync_state = 'quorum'$q$, 60);

INSERT INTO especie (nombre_comun, nombre_cientifico, humedad_ideal_min, humedad_ideal_max,
                     frecuencia_riego_dias, luz, temp_min, temp_max, fuente)
VALUES ('Especie A11', 'Plantae a11', 40, 60, 7, 'indirecta', 15, 28, 'Dato de prueba A11');
-- Reserva del correo (el trigger hace que este COMMIT espere a un suscriptor).
INSERT INTO directorio_correo (correo_hmac, region_id, usuario_id)
VALUES (repeat('e', 64), 1, :u1), (repeat('d', 64), 2, :u2);
SELECT pg_temp.verifica('04 reserva escrita en el escritor', (SELECT count(*) FROM directorio_correo
       WHERE usuario_id IN (:u1, :u2)) = 2);

-- =====================================================================
\echo '=== 2. Norte (primario de la región 1) ==='
-- =====================================================================
\connect :c_norte
\ir _ayudantes.sql
SET search_path TO app;

SELECT pg_temp.espera('05 la especie nueva ya está en Norte',
       $q$SELECT EXISTS (SELECT 1 FROM app.especie WHERE nombre_cientifico = 'Plantae a11')$q$);

-- La API escribe en su región: usuaria de Chihuahua (estado 8), una
-- planta, un riego con el procedimiento de A5 y una lectura de humedad
-- baja que dispara la alerta de A6.
SET ROLE plantas_api;
INSERT INTO usuario (region_id, usuario_id, nombre, apellidos, correo, password_hash, estado_id)
VALUES (1, :u1, 'Norteña', 'A11', 'n11@ejemplo.com', repeat('x', 64), 8);
INSERT INTO planta (region_id, planta_id, usuario_id, especie_id, apodo, tipo_espacio)
SELECT 1, :p1, :u1, especie_id, 'Cactus del patio', 'patio'
FROM especie WHERE nombre_cientifico = 'Plantae a11';
CALL sp_registrar_riego(1::smallint, :p1, 150);
UPDATE planta SET humedad_actual = 10, fecha_ultima_lectura = now() WHERE planta_id = :p1;

SELECT pg_temp.debe_fallar('06 RLS: en Norte la API NO puede escribir filas de la región 2',
  $q$INSERT INTO usuario (region_id, nombre, apellidos, correo, password_hash, estado_id)
     VALUES (2, 'X', 'Y', 'x11@ejemplo.com', repeat('x', 64), 9)$q$, '42501');
SELECT pg_temp.debe_fallar('07 la API NO puede escribir directo en una partición',
  $q$INSERT INTO usuario_r1 (region_id, nombre, apellidos, correo, password_hash, estado_id)
     VALUES (1, 'X', 'Y', 'z11@ejemplo.com', repeat('x', 64), 8)$q$, '42501');
RESET ROLE;

SELECT pg_temp.verifica('08 en Norte quedó 1 alerta de humedad baja (trigger de A6)',
       (SELECT count(*) FROM alerta WHERE planta_id = :p1 AND tipo = 'humedad_baja') = 1);

-- =====================================================================
\echo '=== 3. Centro (copia de la región 1, primario de la región 2) ==='
-- =====================================================================
\connect :c_centro
\ir _ayudantes.sql
SET search_path TO app;

SELECT pg_temp.espera('09 la usuaria de Norte llegó a su copia en Centro (usuario_r1)',
       $q$SELECT EXISTS (SELECT 1 FROM app.usuario_r1 WHERE usuario_id = 'a1100000-0000-0000-0000-000000000001')$q$);
SELECT pg_temp.espera('10 también su planta, su riego y su alerta',
       $q$SELECT (SELECT count(*) FROM app.planta_r1  WHERE planta_id = 'a1100000-0000-0000-0000-0000000000f1') = 1
             AND (SELECT count(*) FROM app.cuidado_r1 WHERE planta_id = 'a1100000-0000-0000-0000-0000000000f1' AND tipo = 'riego') = 1
             AND (SELECT count(*) FROM app.alerta_r1  WHERE planta_id = 'a1100000-0000-0000-0000-0000000000f1') = 1$q$);
SELECT pg_temp.verifica('11 la alerta NO se duplicó en la copia (los triggers no corren al replicar)',
       (SELECT count(*) FROM alerta WHERE planta_id = :p1) = 1);
SELECT pg_temp.verifica('12 la auditoría es local: Centro no tiene la auditoría de Norte',
       NOT EXISTS (SELECT 1 FROM auditoria WHERE registro_id IN (:u1, :p1)));
SELECT pg_temp.espera('13 el directorio y la especie llegaron a Centro',
       $q$SELECT (SELECT count(*) FROM app.directorio_correo WHERE correo_hmac IN (repeat('e', 64), repeat('d', 64))) = 2
             AND EXISTS (SELECT 1 FROM app.especie WHERE nombre_cientifico = 'Plantae a11')$q$);

SET ROLE plantas_api;
SELECT pg_temp.debe_fallar('14 RLS: en Centro la API NO puede crear filas en la copia de la región 1',
  $q$INSERT INTO usuario (region_id, nombre, apellidos, correo, password_hash, estado_id)
     VALUES (1, 'X', 'Y', 'c11@ejemplo.com', repeat('x', 64), 8)$q$, '42501');
-- Intento de modificar la copia: RLS lo filtra (UPDATE 0, sin error).
UPDATE planta SET apodo = 'hackeo' WHERE planta_id = :p1;
\if :centro_es_escritor
\else
SELECT pg_temp.debe_fallar('15 RLS: Centro no es el escritor, la API NO puede escribir el directorio',
  $q$INSERT INTO directorio_correo (correo_hmac, region_id, usuario_id)
     VALUES (repeat('9', 64), 2, gen_random_uuid())$q$, '42501');
\endif
-- La API sí escribe en la región de Centro: usuario de Querétaro (estado 22).
INSERT INTO usuario (region_id, usuario_id, nombre, apellidos, correo, password_hash, estado_id)
VALUES (2, :u2, 'Queretana', 'A11', 'c12@ejemplo.com', repeat('x', 64), 22);
RESET ROLE;
SELECT pg_temp.verifica('16 RLS: en Centro la API NO pudo modificar la copia de la región 1 (UPDATE 0)',
       (SELECT apodo FROM planta WHERE planta_id = :p1) = 'Cactus del patio');
SELECT pg_temp.verifica('17 en Centro la API sí escribe en su propia región',
       EXISTS (SELECT 1 FROM usuario_r2 WHERE usuario_id = :u2));

-- =====================================================================
\echo '=== 4. Sur (copia de la región 2) ==='
-- =====================================================================
\connect :c_sur
\ir _ayudantes.sql
SET search_path TO app;

SELECT pg_temp.espera('18 el usuario de Centro llegó a su copia en Sur (usuario_r2)',
       $q$SELECT EXISTS (SELECT 1 FROM app.usuario_r2 WHERE usuario_id = 'a1100000-0000-0000-0000-000000000002')$q$);
SELECT pg_temp.verifica('19 Sur NO guarda la región 1 (no es su copia en el anillo)',
       NOT EXISTS (SELECT 1 FROM usuario WHERE usuario_id = :u1));
SELECT pg_temp.espera('20 el directorio también llegó a Sur',
       $q$SELECT (SELECT count(*) FROM app.directorio_correo WHERE correo_hmac IN (repeat('e', 64), repeat('d', 64))) = 2$q$);

-- =====================================================================
\echo '=== 5. Actualizaciones y borrados también se replican ==='
-- =====================================================================
\connect :c_norte
\ir _ayudantes.sql
UPDATE app.planta SET apodo = 'Cactus renombrado' WHERE planta_id = :p1;

\connect :c_centro
\ir _ayudantes.sql
SELECT pg_temp.espera('21 el UPDATE en Norte llegó a la copia en Centro',
       $q$SELECT EXISTS (SELECT 1 FROM app.planta_r1 WHERE apodo = 'Cactus renombrado')$q$);
-- Borra su propio usuario de prueba (región 2).
DELETE FROM app.usuario WHERE usuario_id = :u2;

\connect :c_norte
\ir _ayudantes.sql
-- Borra la usuaria de prueba de la región 1 (en cascada: planta, riego, alerta).
DELETE FROM app.usuario WHERE usuario_id = :u1;

\connect :c_centro
\ir _ayudantes.sql
SELECT pg_temp.espera('22 el borrado en cascada de Norte llegó a la copia en Centro',
       $q$SELECT NOT EXISTS (SELECT 1 FROM app.usuario_r1 WHERE usuario_id = 'a1100000-0000-0000-0000-000000000001')
             AND NOT EXISTS (SELECT 1 FROM app.planta_r1  WHERE planta_id  = 'a1100000-0000-0000-0000-0000000000f1')
             AND NOT EXISTS (SELECT 1 FROM app.alerta_r1  WHERE planta_id  = 'a1100000-0000-0000-0000-0000000000f1')$q$);

\connect :c_sur
\ir _ayudantes.sql
SELECT pg_temp.espera('23 el borrado en Centro llegó a la copia en Sur',
       $q$SELECT NOT EXISTS (SELECT 1 FROM app.usuario_r2 WHERE usuario_id = 'a1100000-0000-0000-0000-000000000002')$q$);

-- Limpieza de las globales en el escritor (cuando ya no hay plantas de esa especie).
\connect :c_escritor
\ir _ayudantes.sql
SELECT pg_temp.espera('24 ya no quedan plantas de la especie de prueba en el escritor',
       $q$SELECT NOT EXISTS (SELECT 1 FROM app.planta p JOIN app.especie e USING (especie_id)
                             WHERE e.nombre_cientifico = 'Plantae a11')$q$);
DELETE FROM app.directorio_correo WHERE correo_hmac IN (repeat('e', 64), repeat('d', 64));
DELETE FROM app.especie WHERE nombre_cientifico = 'Plantae a11';

\connect :c_sur
\ir _ayudantes.sql
SELECT pg_temp.espera('25 el borrado del directorio y la especie llegó a Sur',
       $q$SELECT NOT EXISTS (SELECT 1 FROM app.directorio_correo WHERE correo_hmac IN (repeat('e', 64), repeat('d', 64)))
             AND NOT EXISTS (SELECT 1 FROM app.especie WHERE nombre_cientifico = 'Plantae a11')$q$);

\echo 'Pruebas de A11 terminadas: si todas dicen OK, la replicación cumple.'
