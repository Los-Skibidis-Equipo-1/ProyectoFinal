-- =====================================================================
-- A11 (1 de 3) · Seguridad de la replicación: cuenta de replicación,
--               RLS en las copias y directorio síncrono
-- PostgreSQL 16 · Decisión de diseño: docs/registro-decisiones.md (D-01)
-- Responsable: Alexa Yalee Sánchez Tejeda
-- IA: generado y revisado (Claude) — ver docs/bitacora-ia.md
--
-- Se corre EN CADA NODO, después de 01 a 07:
--   psql -U postgres -d plantas -v escritor=norte -v pass_replica=... -f db/08_rls_replicacion.sql
--     escritor     = nodo que escribe las tablas globales (norte, centro o sur; D-01 §4)
--     pass_replica = contraseña de la cuenta plantas_replica (PG_PASS_REPLICA en .env)
--
-- Qué hace:
--   1. Crea la cuenta plantas_replica (la usan las suscripciones para leer
--      del nodo de origen). Solo puede leer las tablas que se replican.
--   2. Marca si este nodo es el escritor de las globales (app.es_escritor_globales).
--   3. RLS en las 5 tablas fragmentadas (D-01 §9): la API lee todo, pero
--      solo escribe filas de las regiones que atiende este nodo.
--   4. RLS en directorio_correo: la API solo lo escribe en el nodo escritor.
--   5. Directorio síncrono (D-01 §5): un trigger pide synchronous_commit = on
--      en cualquier transacción que toque el directorio; en el escritor,
--      synchronous_standby_names = 'ANY 1 (...)' y por defecto 'local'.
-- =====================================================================

\set ON_ERROR_STOP on

\if :{?escritor}
\else
    \echo 'ERROR: falta -v escritor=<norte|centro|sur>'
    \quit
\endif
\if :{?pass_replica}
\else
    \echo 'ERROR: falta -v pass_replica=<contraseña>'
    \quit
\endif

-- ---------------------------------------------------------------------
-- 1. Cuenta de replicación (los roles son del servidor, D-01 §5 notas)
-- ---------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'plantas_replica') THEN
        CREATE ROLE plantas_replica LOGIN REPLICATION NOSUPERUSER NOCREATEDB NOCREATEROLE;
    END IF;
END;
$$;
ALTER ROLE plantas_replica PASSWORD :'pass_replica';

BEGIN;
SET search_path TO app;

SELECT format('GRANT CONNECT ON DATABASE %I TO plantas_replica', current_database()) \gexec
GRANT USAGE ON SCHEMA app TO plantas_replica;
-- Solo lo que se publica: tablas globales y particiones de los fragmentos.
-- NO auditoria (es local y tiene datos personales).
GRANT SELECT ON region, estado, fragmento, especie, directorio_correo TO plantas_replica;
DO $$
DECLARE t text; r int;
BEGIN
    FOREACH t IN ARRAY ARRAY['usuario', 'planta', 'sensor', 'cuidado', 'alerta'] LOOP
        FOR r IN 1..3 LOOP
            EXECUTE format('GRANT SELECT ON app.%I TO plantas_replica', t || '_r' || r);
        END LOOP;
    END LOOP;
END;
$$;

-- ---------------------------------------------------------------------
-- 2. ¿Este nodo es el escritor de las globales?
-- ---------------------------------------------------------------------
SELECT nodo_primario AS nodo_local
FROM fragmento WHERE region_id = (fn_region_local())[1] \gset
\if :{?nodo_local}
\else
    \echo 'ERROR: este nodo no tiene región configurada; corre antes 07_fragmentacion.sql'
    \quit
\endif
SELECT (:'nodo_local' = :'escritor') AS es_escritor \gset
SELECT format('ALTER DATABASE %I SET app.es_escritor_globales = %L',
              current_database(), CASE WHEN :'es_escritor' THEN 'on' ELSE 'off' END) \gexec

-- ---------------------------------------------------------------------
-- 3. RLS en las tablas fragmentadas (D-01 §9)
--    * SELECT: la API y los reportes leen todo (también las copias).
--    * INSERT/UPDATE/DELETE: la API solo toca filas de sus regiones.
--      (SELECT fn_region_local()) se evalúa una vez por consulta.
--    * Sin FORCE: el dueño (plantas_owner) y el superusuario que aplica
--      la suscripción no pasan por las políticas.
--    * Acceso directo a una partición: la API ya no tiene permisos
--      sobre las particiones (A7 solo dio permisos sobre la tabla padre).
-- ---------------------------------------------------------------------
DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['usuario', 'planta', 'sensor', 'cuidado', 'alerta'] LOOP
        EXECUTE format('ALTER TABLE app.%I ENABLE ROW LEVEL SECURITY', t);

        EXECUTE format('DROP POLICY IF EXISTS pol_leer ON app.%I', t);
        EXECUTE format('DROP POLICY IF EXISTS pol_insertar ON app.%I', t);
        EXECUTE format('DROP POLICY IF EXISTS pol_actualizar ON app.%I', t);
        EXECUTE format('DROP POLICY IF EXISTS pol_borrar ON app.%I', t);

        EXECUTE format($p$CREATE POLICY pol_leer ON app.%I FOR SELECT
                         TO plantas_app, plantas_lectura USING (true)$p$, t);
        EXECUTE format($p$CREATE POLICY pol_insertar ON app.%I FOR INSERT TO plantas_app
                         WITH CHECK (region_id = ANY ((SELECT app.fn_region_local())::smallint[]))$p$, t);
        EXECUTE format($p$CREATE POLICY pol_actualizar ON app.%I FOR UPDATE TO plantas_app
                         USING      (region_id = ANY ((SELECT app.fn_region_local())::smallint[]))
                         WITH CHECK (region_id = ANY ((SELECT app.fn_region_local())::smallint[]))$p$, t);
        EXECUTE format($p$CREATE POLICY pol_borrar ON app.%I FOR DELETE TO plantas_app
                         USING (region_id = ANY ((SELECT app.fn_region_local())::smallint[]))$p$, t);
    END LOOP;
END;
$$;

-- ---------------------------------------------------------------------
-- 4. RLS en el directorio: en un nodo suscriptor la API solo lo lee.
-- ---------------------------------------------------------------------
ALTER TABLE directorio_correo ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS pol_dir_leer     ON directorio_correo;
DROP POLICY IF EXISTS pol_dir_escribir ON directorio_correo;
CREATE POLICY pol_dir_leer ON directorio_correo FOR SELECT
    TO plantas_app USING (true);
CREATE POLICY pol_dir_escribir ON directorio_correo FOR ALL
    TO plantas_app
    USING      (current_setting('app.es_escritor_globales', true) = 'on')
    WITH CHECK (current_setting('app.es_escritor_globales', true) = 'on');

-- ---------------------------------------------------------------------
-- 5. Directorio síncrono (D-01 §5)
--    Cualquier transacción que escriba el directorio pide, al hacer
--    COMMIT, esperar a que un suscriptor confirme. Lo demás queda en el
--    valor por defecto del escritor (local = asíncrono).
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_directorio_sincrono()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    PERFORM set_config('synchronous_commit', 'on', true);   -- true = solo esta transacción
    RETURN NULL;
END;
$$;
ALTER FUNCTION trg_directorio_sincrono() OWNER TO plantas_owner;

DROP TRIGGER IF EXISTS tg_directorio_sincrono ON directorio_correo;
CREATE TRIGGER tg_directorio_sincrono
    AFTER INSERT OR UPDATE OR DELETE ON directorio_correo
    FOR EACH STATEMENT EXECUTE FUNCTION trg_directorio_sincrono();

COMMIT;

-- Configuración del servidor (ALTER SYSTEM no va dentro de una transacción).
\if :es_escritor
    ALTER SYSTEM SET synchronous_commit = 'local';
    SELECT format('ALTER SYSTEM SET synchronous_standby_names = %L',
                  'ANY 1 (' || string_agg('sub_glob_' || nodo_primario, ', ' ORDER BY region_id) || ')')
    FROM app.fragmento WHERE nodo_primario <> :'escritor' \gexec
\else
    ALTER SYSTEM RESET synchronous_standby_names;
    ALTER SYSTEM RESET synchronous_commit;
\endif
SELECT pg_reload_conf() AS configuracion_recargada \gset

\echo 'A11 (1/3) listo en el nodo' :nodo_local '- escritor de las globales:' :es_escritor
