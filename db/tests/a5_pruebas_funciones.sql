-- =====================================================================
-- A5 · Pruebas del procedimiento y las funciones
-- IA: generado y revisado (Claude) — ver docs/bitacora-ia.md
--
--   "OK"    = el resultado es el esperado.
--   "FALLO" = el resultado no es el esperado (el script se detiene ahí).
-- Al final hace ROLLBACK: no deja datos de prueba en la base.
--
-- Cómo correrlo (después de 01, 02, 03 y 04):
--   psql -U postgres -d plantas -f db/tests/a5_pruebas_funciones.sql
-- =====================================================================

\set ON_ERROR_STOP on
\pset tuples_only on

BEGIN;
SET search_path TO app;

-- ---------------------------------------------------------------------
-- Ayudantes
-- ---------------------------------------------------------------------
-- Comprueba que una condición sea verdadera.
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

-- Ejecuta una sentencia que DEBE fallar con un SQLSTATE en particular.
CREATE FUNCTION pg_temp.debe_fallar(prueba text, sentencia text, sqlstate_esperado text)
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    BEGIN
        EXECUTE sentencia;
    EXCEPTION WHEN OTHERS THEN
        IF SQLSTATE = sqlstate_esperado THEN
            RAISE NOTICE 'OK    %  (%: %)', prueba, SQLSTATE, SQLERRM;
            RETURN;
        END IF;
        RAISE EXCEPTION 'FALLO %  -> falló con % (%), se esperaba %',
            prueba, SQLSTATE, SQLERRM, sqlstate_esperado;
    END;
    RAISE EXCEPTION 'FALLO %  -> no falló y debía fallar', prueba;
END;
$$;

-- ---------------------------------------------------------------------
-- Datos de prueba: una especie que se riega cada 7 días, una usuaria
-- del Centro (CDMX), una planta activa registrada hace 30 días, una
-- planta fallecida y un recordatorio de riego pendiente.
-- ---------------------------------------------------------------------
INSERT INTO especie (nombre_comun, nombre_cientifico, humedad_ideal_min, humedad_ideal_max,
                     frecuencia_riego_dias, luz, temp_min, temp_max, fuente)
VALUES ('Especie A5', 'Plantae a5', 40, 60, 7, 'indirecta', 15, 28, 'Dato de prueba A5');

INSERT INTO usuario (region_id, usuario_id, nombre, apellidos, correo, password_hash, estado_id)
VALUES (2, 'aaaaaaaa-0000-0000-0000-000000000001', 'Usuaria', 'A5',
        'a5@ejemplo.com', repeat('x', 64), 9);

INSERT INTO planta (region_id, planta_id, usuario_id, especie_id, apodo, tipo_espacio,
                    estatus, fecha_registro)
SELECT 2, v.planta_id, 'aaaaaaaa-0000-0000-0000-000000000001', e.especie_id, v.apodo,
       'casa', v.estatus, now() - interval '30 days'
FROM especie e
CROSS JOIN (VALUES ('bbbbbbbb-0000-0000-0000-000000000001'::uuid, 'Activa',    'activa'),
                   ('bbbbbbbb-0000-0000-0000-000000000002'::uuid, 'Fallecida', 'fallecida'))
       AS v(planta_id, apodo, estatus)
WHERE e.nombre_cientifico = 'Plantae a5';

INSERT INTO alerta (region_id, planta_id, tipo, mensaje, fecha_generada)
VALUES (2, 'bbbbbbbb-0000-0000-0000-000000000001', 'riego_pendiente',
        'Toca regar', now() - interval '1 day');

\echo '--- fn_estado_hidratacion ---'
SELECT pg_temp.verifica('01 humedad 30 con rango 40-60 es baja',
       fn_estado_hidratacion(30, 40, 60) = 'baja');
SELECT pg_temp.verifica('02 humedad 50 con rango 40-60 es optima',
       fn_estado_hidratacion(50, 40, 60) = 'optima');
SELECT pg_temp.verifica('03 humedad 75 con rango 40-60 es alta',
       fn_estado_hidratacion(75, 40, 60) = 'alta');
SELECT pg_temp.verifica('04 los bordes (40 y 60) cuentan como optima',
       fn_estado_hidratacion(40, 40, 60) = 'optima' AND fn_estado_hidratacion(60, 40, 60) = 'optima');
SELECT pg_temp.verifica('05 sin lectura (NULL) es sin_dato',
       fn_estado_hidratacion(NULL, 40, 60) = 'sin_dato');

\echo '--- fn_proximo_riego ---'
SELECT pg_temp.verifica('06 planta nunca regada: el riego toca desde su registro (hace 30 días)',
       fn_proximo_riego(2::smallint, 'bbbbbbbb-0000-0000-0000-000000000001')
         = (SELECT fecha_registro FROM planta WHERE planta_id = 'bbbbbbbb-0000-0000-0000-000000000001'));
SELECT pg_temp.verifica('07 planta que no existe devuelve NULL',
       fn_proximo_riego(2::smallint, gen_random_uuid()) IS NULL);

\echo '--- sp_registrar_riego: casos correctos ---'
CALL sp_registrar_riego(2::smallint, 'bbbbbbbb-0000-0000-0000-000000000001', 300,
                        'Riego de prueba', now() - interval '2 days');
SELECT pg_temp.verifica('08 el riego quedó guardado con su cantidad',
       EXISTS (SELECT 1 FROM cuidado
               WHERE planta_id = 'bbbbbbbb-0000-0000-0000-000000000001'
                 AND tipo = 'riego' AND cantidad_ml = 300));
SELECT pg_temp.verifica('09 el recordatorio de riego quedó atendido y con fecha',
       NOT EXISTS (SELECT 1 FROM alerta
                   WHERE planta_id = 'bbbbbbbb-0000-0000-0000-000000000001'
                     AND (estado = 'pendiente' OR fecha_atendida IS NULL)));
SELECT pg_temp.verifica('10 próximo riego = riego de hace 2 días + 7 días (en 5 días)',
       fn_proximo_riego(2::smallint, 'bbbbbbbb-0000-0000-0000-000000000001')
         = (SELECT max(fecha_hora) FROM cuidado
            WHERE planta_id = 'bbbbbbbb-0000-0000-0000-000000000001') + interval '7 days');

-- El parámetro INOUT regresa el id del cuidado creado.
DO $$
DECLARE v_id uuid;
BEGIN
    CALL app.sp_registrar_riego(2::smallint, 'bbbbbbbb-0000-0000-0000-000000000001',
                                NULL, NULL, now(), v_id);
    PERFORM pg_temp.verifica('11 sin cantidad también se registra y regresa el id del cuidado',
            v_id IS NOT NULL AND EXISTS (SELECT 1 FROM app.cuidado WHERE cuidado_id = v_id));
END;
$$;

\echo '--- sp_registrar_riego: casos que deben fallar ---'
SELECT pg_temp.debe_fallar('12 planta que no existe',
  $q$CALL sp_registrar_riego(2::smallint, gen_random_uuid(), 100)$q$, 'P0002');
SELECT pg_temp.debe_fallar('13 planta de otra región (existe en Centro, se pide en Norte)',
  $q$CALL sp_registrar_riego(1::smallint, 'bbbbbbbb-0000-0000-0000-000000000001', 100)$q$, 'P0002');
SELECT pg_temp.debe_fallar('14 planta fallecida',
  $q$CALL sp_registrar_riego(2::smallint, 'bbbbbbbb-0000-0000-0000-000000000002', 100)$q$, '23514');
SELECT pg_temp.debe_fallar('15 cantidad negativa',
  $q$CALL sp_registrar_riego(2::smallint, 'bbbbbbbb-0000-0000-0000-000000000001', -50)$q$, '23514');
SELECT pg_temp.debe_fallar('16 fecha en el futuro',
  $q$CALL sp_registrar_riego(2::smallint, 'bbbbbbbb-0000-0000-0000-000000000001', 100,
                            NULL, now() + interval '1 day')$q$, '23514');
SELECT pg_temp.verifica('17 los intentos fallidos no guardaron nada (siguen siendo 2 riegos)',
       (SELECT count(*) FROM cuidado
        WHERE planta_id = 'bbbbbbbb-0000-0000-0000-000000000001') = 2);

ROLLBACK;

\echo 'Pruebas de A5 terminadas: si todas dicen OK, A5 cumple.'
