-- =====================================================================
-- A6 · Pruebas de los triggers
-- IA: generado y revisado (Claude) — ver docs/bitacora-ia.md
--
-- Cada trigger se demuestra con un INSERT o UPDATE de prueba.
--   "OK"    = el resultado es el esperado.
--   "FALLO" = no lo es (el script se detiene ahí).
-- Al final hace ROLLBACK: no deja datos de prueba en la base.
--
-- Cómo correrlo (después de 01 a 05):
--   psql -U postgres -d plantas -f db/tests/a6_pruebas_triggers.sql
-- =====================================================================

\set ON_ERROR_STOP on
\pset tuples_only on

BEGIN;
SET search_path TO app;

CREATE FUNCTION pg_temp.verifica(prueba text, condicion boolean)
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    IF condicion IS TRUE THEN
        RAISE NOTICE 'OK    %', prueba;
    ELSE
        RAISE EXCEPTION 'FALLO %', prueba;
    END IF;
END;
$$;

-- Cuenta alertas de la planta de prueba por tipo y estado.
CREATE FUNCTION pg_temp.alertas(p_tipo text, p_estado text)
RETURNS bigint LANGUAGE sql AS $$
    SELECT count(*) FROM app.alerta
    WHERE planta_id = 'cccccccc-0000-0000-0000-000000000001'
      AND tipo = p_tipo AND estado = p_estado;
$$;

-- La API diría quién es el usuario de la app que hace los cambios.
SET LOCAL app.usuario_id = 'dddddddd-0000-0000-0000-000000000001';

-- ---------------------------------------------------------------------
-- Datos de prueba: especie con humedad ideal 40–60 %, usuaria del
-- Centro y una planta activa. Las fechas se ponen en el pasado para
-- poder ver que el trigger las cambia.
-- ---------------------------------------------------------------------
INSERT INTO especie (nombre_comun, nombre_cientifico, humedad_ideal_min, humedad_ideal_max,
                     frecuencia_riego_dias, luz, temp_min, temp_max, fuente)
VALUES ('Especie A6', 'Plantae a6', 40, 60, 7, 'indirecta', 15, 28, 'Dato de prueba A6');

INSERT INTO usuario (region_id, usuario_id, nombre, apellidos, correo, password_hash, estado_id,
                     fecha_registro, fecha_actualizacion)
VALUES (2, 'cccccccc-0000-0000-0000-0000000000aa', 'Usuaria', 'A6', 'a6@ejemplo.com',
        'scrypt$secreto$' || repeat('x', 64), 9,
        now() - interval '10 days', now() - interval '10 days');

INSERT INTO planta (region_id, planta_id, usuario_id, especie_id, apodo, tipo_espacio,
                    fecha_registro, fecha_actualizacion)
SELECT 2, 'cccccccc-0000-0000-0000-000000000001', 'cccccccc-0000-0000-0000-0000000000aa',
       especie_id, 'Helecho del baño', 'departamento',
       now() - interval '10 days', now() - interval '10 days'
FROM especie WHERE nombre_cientifico = 'Plantae a6';

\echo '--- 1. Fecha de actualización ---'
UPDATE usuario SET nombre = 'Usuaria cambiada'
WHERE usuario_id = 'cccccccc-0000-0000-0000-0000000000aa';
SELECT pg_temp.verifica('01 UPDATE de usuario pone fecha_actualizacion = ahora',
       (SELECT fecha_actualizacion FROM usuario
        WHERE usuario_id = 'cccccccc-0000-0000-0000-0000000000aa') = now());

UPDATE usuario SET fecha_actualizacion = '2000-01-01'
WHERE usuario_id = 'cccccccc-0000-0000-0000-0000000000aa';
SELECT pg_temp.verifica('02 no se puede poner una fecha_actualizacion falsa',
       (SELECT fecha_actualizacion FROM usuario
        WHERE usuario_id = 'cccccccc-0000-0000-0000-0000000000aa') = now());

UPDATE planta SET apodo = 'Helecho grande'
WHERE planta_id = 'cccccccc-0000-0000-0000-000000000001';
SELECT pg_temp.verifica('03 UPDATE de planta también actualiza su fecha',
       (SELECT fecha_actualizacion FROM planta
        WHERE planta_id = 'cccccccc-0000-0000-0000-000000000001') = now());

\echo '--- 2. Alertas por humedad (rango ideal 40–60 %) ---'
UPDATE planta SET humedad_actual = 25, fecha_ultima_lectura = now()
WHERE planta_id = 'cccccccc-0000-0000-0000-000000000001';
SELECT pg_temp.verifica('04 humedad 25 % crea una alerta humedad_baja pendiente',
       pg_temp.alertas('humedad_baja', 'pendiente') = 1);

UPDATE planta SET humedad_actual = 22, fecha_ultima_lectura = now()
WHERE planta_id = 'cccccccc-0000-0000-0000-000000000001';
SELECT pg_temp.verifica('05 otra lectura baja (22 %) no repite la alerta',
       pg_temp.alertas('humedad_baja', 'pendiente') = 1);

UPDATE planta SET humedad_actual = 80, fecha_ultima_lectura = now()
WHERE planta_id = 'cccccccc-0000-0000-0000-000000000001';
SELECT pg_temp.verifica('06 pasa a 80 %: atiende la baja y crea una humedad_alta',
       pg_temp.alertas('humedad_baja', 'pendiente') = 0
       AND pg_temp.alertas('humedad_baja', 'atendida') = 1
       AND pg_temp.alertas('humedad_alta', 'pendiente') = 1);

UPDATE planta SET humedad_actual = 50, fecha_ultima_lectura = now()
WHERE planta_id = 'cccccccc-0000-0000-0000-000000000001';
SELECT pg_temp.verifica('07 vuelve a 50 % (óptima): no quedan alertas de humedad pendientes',
       pg_temp.alertas('humedad_alta', 'pendiente') = 0
       AND pg_temp.alertas('humedad_baja', 'pendiente') = 0);

SELECT pg_temp.verifica('08 el mensaje de la alerta dice la planta y los valores',
       EXISTS (SELECT 1 FROM alerta
               WHERE planta_id = 'cccccccc-0000-0000-0000-000000000001'
                 AND mensaje = 'Helecho grande: humedad 25.00 % (ideal entre 40.00 y 60.00 %)'));

UPDATE planta SET estatus = 'regalada'
WHERE planta_id = 'cccccccc-0000-0000-0000-000000000001';
UPDATE planta SET humedad_actual = 5, fecha_ultima_lectura = now()
WHERE planta_id = 'cccccccc-0000-0000-0000-000000000001';
SELECT pg_temp.verifica('09 una planta que ya no está activa no genera alertas',
       pg_temp.alertas('humedad_baja', 'pendiente') = 0);
UPDATE planta SET estatus = 'activa'
WHERE planta_id = 'cccccccc-0000-0000-0000-000000000001';

\echo '--- 3. Auditoría ---'
SELECT pg_temp.verifica('10 el INSERT de usuario quedó auditado',
       EXISTS (SELECT 1 FROM auditoria
               WHERE tabla = 'usuario' AND operacion = 'INSERT'
                 AND registro_id = 'cccccccc-0000-0000-0000-0000000000aa'));

SELECT pg_temp.verifica('11 la auditoría NUNCA guarda password_hash',
       NOT EXISTS (SELECT 1 FROM auditoria
                   WHERE tabla = 'usuario'
                     AND (datos_nuevos ? 'password_hash' OR datos_anteriores ? 'password_hash')));

SELECT pg_temp.verifica('12 el UPDATE guarda el valor anterior y el nuevo',
       EXISTS (SELECT 1 FROM auditoria
               WHERE tabla = 'usuario' AND operacion = 'UPDATE'
                 AND datos_anteriores ->> 'nombre' = 'Usuaria'
                 AND datos_nuevos ->> 'nombre' = 'Usuaria cambiada'));

SELECT pg_temp.verifica('13 registra al usuario de la app (SET app.usuario_id)',
       NOT EXISTS (SELECT 1 FROM auditoria
                   WHERE registro_id IN ('cccccccc-0000-0000-0000-0000000000aa',
                                         'cccccccc-0000-0000-0000-000000000001')
                     AND usuario_app IS DISTINCT FROM 'dddddddd-0000-0000-0000-000000000001'));

SELECT pg_temp.verifica('14 las lecturas de humedad (solo humedad y fecha) NO se auditan',
       NOT EXISTS (SELECT 1 FROM auditoria
                   WHERE tabla = 'planta' AND operacion = 'UPDATE'
                     AND datos_anteriores ->> 'apodo' = datos_nuevos ->> 'apodo'
                     AND datos_anteriores ->> 'estatus' = datos_nuevos ->> 'estatus'));

SELECT pg_temp.verifica('15 los cambios reales de la planta sí se auditan (apodo y 2 de estatus)',
       (SELECT count(*) FROM auditoria
        WHERE tabla = 'planta' AND operacion = 'UPDATE'
          AND registro_id = 'cccccccc-0000-0000-0000-000000000001') = 3);

DELETE FROM usuario WHERE usuario_id = 'cccccccc-0000-0000-0000-0000000000aa';
SELECT pg_temp.verifica('16 borrar la usuaria audita su DELETE y el de su planta (cascada)',
       (SELECT count(*) FROM auditoria
        WHERE operacion = 'DELETE'
          AND registro_id IN ('cccccccc-0000-0000-0000-0000000000aa',
                              'cccccccc-0000-0000-0000-000000000001')) = 2);

UPDATE especie SET cuidados = 'Rociar las hojas' WHERE nombre_cientifico = 'Plantae a6';
SELECT pg_temp.verifica('17 los cambios al catálogo de especies se auditan',
       EXISTS (SELECT 1 FROM auditoria
               WHERE tabla = 'especie' AND operacion = 'UPDATE'
                 AND datos_nuevos ->> 'cuidados' = 'Rociar las hojas'));

ROLLBACK;

\echo 'Pruebas de A6 terminadas: si todas dicen OK, A6 cumple.'
