-- =====================================================================
-- A7 · Roles, privilegios y vistas con datos enmascarados
-- PostgreSQL 16
-- Responsable: Alexa Yalee Sánchez Tejeda
-- IA: generado y revisado (Claude) — ver docs/bitacora-ia.md
--
-- Modelo (principio de mínimo privilegio):
--
--   Grupo (NOLOGIN)   Para quién              Puede
--   ----------------  ----------------------  ---------------------------------------------
--   plantas_owner     dueño de los objetos    todo (crear, cambiar y borrar tablas)
--   plantas_app       la API de Python        leer/escribir datos de la app; NO DDL,
--                                             NO TRUNCATE, NO auditoría, NO catálogo
--   plantas_lectura   reportes y gráficas     solo vistas enmascaradas y catálogos
--   plantas_auditor   revisión de seguridad   solo leer la auditoría
--
--   Cuenta (LOGIN)    Pertenece a
--   ----------------  ---------------------
--   plantas_admin     plantas_owner + plantas_auditor   (administración)
--   plantas_api       plantas_app                       (cuenta de servicio)
--   plantas_reportes  plantas_lectura                   (pandas / gráficas)
--
-- Las contraseñas NO están en este archivo ni en el repo: se pasan al
-- correrlo con -v y deben venir del .env (que no se sube a git).
--
-- Cómo correrlo (después de 01 a 05, con un superusuario):
--   psql -U postgres -d plantas \
--        -v pass_admin=... -v pass_api=... -v pass_reportes=... \
--        -f db/06_roles.sql
-- Se puede correr varias veces. Si se vuelve a correr 01_esquema.sql,
-- hay que volver a correr este archivo (los permisos se pierden al
-- borrar y crear de nuevo las tablas).
-- =====================================================================

\set ON_ERROR_STOP on

-- Las 3 contraseñas son obligatorias.
\if :{?pass_admin}
\else
    \echo 'ERROR: falta -v pass_admin=<contraseña>'
    \quit
\endif
\if :{?pass_api}
\else
    \echo 'ERROR: falta -v pass_api=<contraseña>'
    \quit
\endif
\if :{?pass_reportes}
\else
    \echo 'ERROR: falta -v pass_reportes=<contraseña>'
    \quit
\endif

BEGIN;

-- =====================================================================
-- 1. Roles (los roles son de todo el servidor; se crean solo si no existen)
-- =====================================================================
DO $$
DECLARE
    r record;
BEGIN
    FOR r IN SELECT * FROM (VALUES
        ('plantas_owner',    false),
        ('plantas_app',      false),
        ('plantas_lectura',  false),
        ('plantas_auditor',  false),
        ('plantas_admin',    true),
        ('plantas_api',      true),
        ('plantas_reportes', true)) AS t(nombre, login)
    LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r.nombre) THEN
            EXECUTE format('CREATE ROLE %I %s NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION',
                           r.nombre, CASE WHEN r.login THEN 'LOGIN' ELSE 'NOLOGIN' END);
        END IF;
    END LOOP;
END;
$$;

-- Contraseñas (se guardan cifradas con SCRAM-SHA-256).
ALTER ROLE plantas_admin    PASSWORD :'pass_admin';
ALTER ROLE plantas_api      PASSWORD :'pass_api';
ALTER ROLE plantas_reportes PASSWORD :'pass_reportes';

-- La API no necesita más de 50 conexiones; limita el daño si se abusa.
ALTER ROLE plantas_api CONNECTION LIMIT 50;

-- Pertenencia de las cuentas a los grupos.
GRANT plantas_owner, plantas_auditor TO plantas_admin;
GRANT plantas_app      TO plantas_api;
GRANT plantas_lectura  TO plantas_reportes;

-- Al conectarse, buscan las tablas en el esquema app.
ALTER ROLE plantas_admin    SET search_path = app, public;
ALTER ROLE plantas_api      SET search_path = app, public;
ALTER ROLE plantas_reportes SET search_path = app, public;

-- =====================================================================
-- 2. Nadie entra a la base si no tiene un rol del sistema
-- =====================================================================
DO $$
BEGIN
    EXECUTE format('REVOKE ALL ON DATABASE %I FROM PUBLIC', current_database());
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO plantas_owner, plantas_app, plantas_lectura, plantas_auditor',
                   current_database());
END;
$$;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;

-- =====================================================================
-- 3. plantas_owner es dueño de todo el esquema app
--    (así el superusuario postgres solo se usa para instalar, y la
--    función SECURITY DEFINER de auditoría corre como plantas_owner,
--    no como superusuario)
-- =====================================================================
ALTER SCHEMA app OWNER TO plantas_owner;

DO $$
DECLARE
    r record;
BEGIN
    -- Tablas, particiones y vistas (las secuencias de las columnas
    -- IDENTITY cambian de dueño junto con su tabla).
    FOR r IN
        SELECT c.relname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'app' AND c.relkind IN ('r', 'p', 'v')
    LOOP
        EXECUTE format('ALTER TABLE app.%I OWNER TO plantas_owner', r.relname);
    END LOOP;

    -- Funciones y procedimientos.
    FOR r IN
        SELECT p.oid::regprocedure AS firma, p.prokind
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'app'
    LOOP
        EXECUTE format('ALTER %s %s OWNER TO plantas_owner',
                       CASE r.prokind WHEN 'p' THEN 'PROCEDURE' ELSE 'FUNCTION' END, r.firma);
    END LOOP;
END;
$$;

SET search_path TO app;

-- =====================================================================
-- 4. Vistas con datos enmascarados (para plantas_lectura)
--    La vista es de plantas_owner: quien la consulta NO necesita permiso
--    sobre la tabla, solo sobre la vista. security_barrier evita que un
--    filtro malicioso "espíe" filas antes de aplicar la vista.
-- =====================================================================
CREATE OR REPLACE FUNCTION fn_enmascarar_correo(p_correo text)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
    -- alexa@ejemplo.com  ->  a***@ejemplo.com
    SELECT left(split_part(p_correo, '@', 1), 1) || '***@' || split_part(p_correo, '@', 2);
$$;
ALTER FUNCTION fn_enmascarar_correo(text) OWNER TO plantas_owner;

-- Usuario sin contraseña, con nombre, apellidos y correo enmascarados.
CREATE OR REPLACE VIEW vw_usuario_enmascarado WITH (security_barrier = true) AS
SELECT region_id,
       usuario_id,
       left(nombre, 1) || '.'      AS nombre,
       left(apellidos, 1) || '***' AS apellidos,
       fn_enmascarar_correo(correo) AS correo,
       rol,
       estado_id,
       activo,
       fecha_registro
FROM usuario;
ALTER VIEW vw_usuario_enmascarado OWNER TO plantas_owner;

-- Planta sin la descripción de su ubicación en la casa.
CREATE OR REPLACE VIEW vw_planta_reporte WITH (security_barrier = true) AS
SELECT region_id, planta_id, usuario_id, especie_id, tipo_espacio, estatus,
       humedad_actual, fecha_ultima_lectura, fecha_registro
FROM planta;
ALTER VIEW vw_planta_reporte OWNER TO plantas_owner;

-- Cuidado sin las notas (texto libre que puede traer datos personales).
CREATE OR REPLACE VIEW vw_cuidado_reporte WITH (security_barrier = true) AS
SELECT region_id, cuidado_id, planta_id, tipo, fecha_hora, cantidad_ml
FROM cuidado;
ALTER VIEW vw_cuidado_reporte OWNER TO plantas_owner;

-- =====================================================================
-- 5. Privilegios
--    Primero se quita todo y luego se da solo lo necesario.
-- =====================================================================
REVOKE ALL ON ALL TABLES    IN SCHEMA app FROM PUBLIC, plantas_app, plantas_lectura, plantas_auditor;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA app FROM PUBLIC, plantas_app, plantas_lectura, plantas_auditor;
-- Por omisión PostgreSQL deja ejecutar cualquier función a todos (PUBLIC).
REVOKE ALL ON ALL ROUTINES  IN SCHEMA app FROM PUBLIC;

GRANT USAGE ON SCHEMA app TO plantas_app, plantas_lectura, plantas_auditor;

-- ---- plantas_app (API) ----
-- Datos de la app: leer, insertar, actualizar y borrar. Sin TRUNCATE,
-- sin REFERENCES, sin TRIGGER y sin DDL (no es dueña de nada).
GRANT SELECT, INSERT, UPDATE, DELETE
    ON usuario, planta, sensor, cuidado, alerta, directorio_correo
    TO plantas_app;
-- Catálogos: solo leer (el catálogo de especies lo administra plantas_admin).
GRANT SELECT ON region, estado, especie TO plantas_app;
-- Funciones y procedimiento de A5.
GRANT EXECUTE ON FUNCTION  fn_estado_hidratacion(numeric, numeric, numeric) TO plantas_app, plantas_lectura;
GRANT EXECUTE ON FUNCTION  fn_proximo_riego(smallint, uuid)                TO plantas_app;
GRANT EXECUTE ON PROCEDURE sp_registrar_riego(smallint, uuid, integer, varchar, timestamptz, uuid)
    TO plantas_app;
-- auditoria: NINGÚN permiso. Los triggers escriben en ella porque su
-- función es SECURITY DEFINER (corre como plantas_owner).

-- ---- plantas_lectura (reportes) ----
GRANT SELECT ON vw_usuario_enmascarado, vw_planta_reporte, vw_cuidado_reporte TO plantas_lectura;
-- Las funciones que usa una vista se revisan con los permisos de QUIEN
-- CONSULTA, no del dueño de la vista: hay que dar EXECUTE también.
GRANT EXECUTE ON FUNCTION fn_enmascarar_correo(text) TO plantas_lectura;
GRANT SELECT ON alerta, especie, region, estado TO plantas_lectura;

-- ---- plantas_auditor ----
GRANT SELECT ON auditoria TO plantas_auditor;

-- Objetos que se creen en el futuro: tampoco se pueden ejecutar por todos.
ALTER DEFAULT PRIVILEGES FOR ROLE plantas_owner IN SCHEMA app
    REVOKE EXECUTE ON ROUTINES FROM PUBLIC;

COMMIT;

\echo 'Roles, privilegios y vistas de A7 creados correctamente.'
