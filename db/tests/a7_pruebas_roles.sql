-- =====================================================================
-- A7 · Pruebas de roles y privilegios
-- IA: generado y revisado (Claude) — ver docs/bitacora-ia.md
--
-- Se corre como superusuario y usa SET ROLE para "hacerse pasar" por
-- cada cuenta. Lo que una cuenta no debe poder hacer tiene que fallar
-- con SQLSTATE 42501 (insufficient_privilege).
--   "OK"    = resultado esperado.   "FALLO" = no lo es (se detiene).
-- Al final hace ROLLBACK: no deja cambios (ni tablas borradas).
--
-- Cómo correrlo (después de 01 a 06):
--   psql -U postgres -d plantas -f db/tests/a7_pruebas_roles.sql
-- =====================================================================

\set ON_ERROR_STOP on
\pset tuples_only on

BEGIN;
SET search_path TO app;
-- Los datos de prueba son de la región 2 (Centro). Con RLS (A11) la API
-- solo escribe en las regiones del nodo, así que la prueba se declara
-- de esa región, sin importar en qué nodo corra.
SET LOCAL app.region_local = '2';

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

-- Debe fallar por falta de permiso (42501).
CREATE FUNCTION pg_temp.sin_permiso(prueba text, sentencia text)
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    BEGIN
        EXECUTE sentencia;
    EXCEPTION WHEN insufficient_privilege THEN
        RAISE NOTICE 'OK    % (como %)  (%)', prueba, current_user, SQLERRM;
        RETURN;
    END;
    RAISE EXCEPTION 'FALLO % -> % SÍ pudo hacerlo', prueba, current_user;
END;
$$;

-- Debe funcionar sin error.
CREATE FUNCTION pg_temp.con_permiso(prueba text, sentencia text)
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    EXECUTE sentencia;
    RAISE NOTICE 'OK    % (como %)', prueba, current_user;
EXCEPTION WHEN OTHERS THEN
    RAISE EXCEPTION 'FALLO % -> % no pudo: %', prueba, current_user, SQLERRM;
END;
$$;

GRANT EXECUTE ON FUNCTION pg_temp.verifica(text, boolean),
                          pg_temp.sin_permiso(text, text),
                          pg_temp.con_permiso(text, text) TO PUBLIC;

-- Datos de prueba (como superusuario).
INSERT INTO especie (nombre_comun, nombre_cientifico, humedad_ideal_min, humedad_ideal_max,
                     frecuencia_riego_dias, luz, temp_min, temp_max, fuente)
VALUES ('Especie A7', 'Plantae a7', 40, 60, 7, 'indirecta', 15, 28, 'Dato de prueba A7');
INSERT INTO usuario (region_id, usuario_id, nombre, apellidos, correo, password_hash, estado_id)
VALUES (2, 'eeeeeeee-0000-0000-0000-000000000001', 'Alexa', 'Sanchez',
        'alexa@ejemplo.com', repeat('x', 64), 9);
INSERT INTO planta (region_id, planta_id, usuario_id, especie_id, apodo, tipo_espacio,
                    ubicacion_descripcion)
SELECT 2, 'eeeeeeee-0000-0000-0000-000000000002', 'eeeeeeee-0000-0000-0000-000000000001',
       especie_id, 'Potus', 'casa', 'recámara de mi hija'
FROM especie WHERE nombre_cientifico = 'Plantae a7';
INSERT INTO cuidado (region_id, planta_id, tipo, cantidad_ml, notas)
VALUES (2, 'eeeeeeee-0000-0000-0000-000000000002', 'riego', 200, 'Mi teléfono es 449 000 0000');

-- =====================================================================
\echo '--- Cuenta de servicio (plantas_api) ---'
-- =====================================================================
SET LOCAL ROLE plantas_api;

SELECT pg_temp.con_permiso('01 leer y actualizar usuarios',
  $q$UPDATE usuario SET nombre = 'Alexa Y.' WHERE usuario_id = 'eeeeeeee-0000-0000-0000-000000000001'$q$);
SELECT pg_temp.con_permiso('02 registrar un riego con el procedimiento de A5',
  $q$CALL sp_registrar_riego(2::smallint, 'eeeeeeee-0000-0000-0000-000000000002', 150)$q$);
SELECT pg_temp.con_permiso('03 la lectura de humedad dispara la alerta (trigger de A6)',
  $q$UPDATE planta SET humedad_actual = 10, fecha_ultima_lectura = now()
     WHERE planta_id = 'eeeeeeee-0000-0000-0000-000000000002'$q$);

SELECT pg_temp.sin_permiso('04 NO puede borrar una tabla (DROP TABLE)',
  $q$DROP TABLE cuidado$q$);
SELECT pg_temp.sin_permiso('05 NO puede vaciar una tabla (TRUNCATE)',
  $q$TRUNCATE alerta$q$);
SELECT pg_temp.sin_permiso('06 NO puede cambiar la estructura (ALTER TABLE)',
  $q$ALTER TABLE usuario ADD COLUMN espia text$q$);
SELECT pg_temp.sin_permiso('07 NO puede crear tablas en el esquema app',
  $q$CREATE TABLE app.tabla_rara (x int)$q$);
SELECT pg_temp.sin_permiso('08 NO puede escribir en la auditoría (falsificar)',
  $q$INSERT INTO auditoria (tabla, operacion, registro_id, datos_nuevos)
     VALUES ('usuario', 'INSERT', 'x', '{}')$q$);
SELECT pg_temp.sin_permiso('09 NO puede borrar la auditoría (borrar huellas)',
  $q$DELETE FROM auditoria$q$);
SELECT pg_temp.sin_permiso('10 NO puede leer la auditoría',
  $q$SELECT count(*) FROM auditoria$q$);
SELECT pg_temp.sin_permiso('11 NO puede modificar el catálogo de especies',
  $q$UPDATE especie SET humedad_ideal_min = 0$q$);
SELECT pg_temp.sin_permiso('12 NO puede darse más permisos ni crear roles',
  $q$CREATE ROLE intruso SUPERUSER$q$);

RESET ROLE;
SELECT pg_temp.verifica('13 aunque la API no puede escribir en la auditoría, sus cambios sí quedaron auditados',
       EXISTS (SELECT 1 FROM auditoria
               WHERE tabla = 'usuario' AND operacion = 'UPDATE'
                 AND registro_id = 'eeeeeeee-0000-0000-0000-000000000001'));
SELECT pg_temp.verifica('14 y la alerta de humedad baja sí se creó',
       EXISTS (SELECT 1 FROM alerta
               WHERE planta_id = 'eeeeeeee-0000-0000-0000-000000000002'
                 AND tipo = 'humedad_baja' AND estado = 'pendiente'));

-- =====================================================================
\echo '--- Cuenta de reportes (plantas_reportes) ---'
-- =====================================================================
SET LOCAL ROLE plantas_reportes;

SELECT pg_temp.sin_permiso('15 NO puede leer la tabla usuario directamente',
  $q$SELECT * FROM usuario$q$);
SELECT pg_temp.sin_permiso('16 NO puede leer las notas de los cuidados',
  $q$SELECT notas FROM cuidado$q$);
SELECT pg_temp.sin_permiso('17 NO puede modificar nada',
  $q$UPDATE alerta SET estado = 'atendida', fecha_atendida = now()$q$);

SELECT pg_temp.verifica('18 en la vista ve el correo, nombre y apellidos enmascarados',
       (SELECT correo = 'a***@ejemplo.com' AND nombre = 'A.' AND apellidos = 'S***'
        FROM vw_usuario_enmascarado
        WHERE usuario_id = 'eeeeeeee-0000-0000-0000-000000000001'));
SELECT pg_temp.verifica('19 las vistas no tienen password_hash, ubicación ni notas',
       NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'app'
                     AND table_name IN ('vw_usuario_enmascarado', 'vw_planta_reporte', 'vw_cuidado_reporte')
                     AND column_name IN ('password_hash', 'ubicacion_descripcion', 'notas')));
SELECT pg_temp.verifica('20 puede hacer reportes con las vistas (riegos por planta)',
       (SELECT count(*) FROM vw_cuidado_reporte
        WHERE planta_id = 'eeeeeeee-0000-0000-0000-000000000002' AND tipo = 'riego') = 2);

RESET ROLE;

-- =====================================================================
\echo '--- Cuenta de administración (plantas_admin) ---'
-- =====================================================================
SET LOCAL ROLE plantas_admin;

SELECT pg_temp.con_permiso('21 puede leer la auditoría',
  $q$SELECT count(*) FROM auditoria$q$);
SELECT pg_temp.con_permiso('22 puede cambiar la estructura (es dueña de los objetos)',
  $q$ALTER TABLE especie ADD COLUMN prueba_a7 text$q$);
SELECT pg_temp.verifica('23 plantas_admin NO es superusuario',
       NOT (SELECT rolsuper FROM pg_roles WHERE rolname = 'plantas_admin'));

RESET ROLE;

SELECT pg_temp.verifica('24 el dueño de las tablas es plantas_owner, no postgres',
       NOT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                   WHERE n.nspname = 'app' AND c.relkind IN ('r', 'p', 'v')
                     AND pg_get_userbyid(c.relowner) <> 'plantas_owner'));

ROLLBACK;

\echo 'Pruebas de A7 terminadas: si todas dicen OK, A7 cumple.'
