-- =====================================================================
-- A9 · Fragmentación horizontal y directorio de fragmentos
-- PostgreSQL 16
-- Responsable: Alexa Yalee Sánchez Tejeda
-- IA: generado y revisado (Claude) — ver docs/bitacora-ia.md
-- Decisión de diseño: docs/registro-decisiones.md (D-01)
--
-- Se corre UNA VEZ EN CADA NODO, diciendo de qué región es ese nodo:
--   psql -U postgres -d plantas -v region=1 -f db/07_fragmentacion.sql   (Norte)
--   psql -U postgres -d plantas -v region=2 -f db/07_fragmentacion.sql   (Centro)
--   psql -U postgres -d plantas -v region=3 -f db/07_fragmentacion.sql   (Sur)
-- Antes: 01 a 06. Se puede correr varias veces.
--
-- Qué agrega:
--   1. directorio_correo.fecha_reserva  -> para detectar reservas a medias (D-01 §6)
--   2. fragmento                        -> qué nodo es primario y cuál copia de cada región (anillo)
--   3. app.region_local                 -> la(s) región(es) que este nodo atiende (D-01 §9)
--   4. fn_region_local()                -> lee ese valor como arreglo, p. ej. {2} o {2,1}
--   5. fn_ubicar_usuario(correo_hmac)   -> el directorio: región y usuario_id de un correo
--   6. vw_reservas_huerfanas            -> reservas sin usuario en este nodo (más de 10 min)
--      vw_usuarios_sin_directorio       -> usuarios de este nodo sin fila en el directorio
--
-- Qué NO hace (D-01): la replicación del anillo y RLS van en A11; la
-- promoción (promover.sh) en A12.
-- =====================================================================

\set ON_ERROR_STOP on

-- La región del nodo es obligatoria y debe ser 1, 2 o 3.
\if :{?region}
\else
    \echo 'ERROR: falta -v region=<1|2|3>  (1 Norte, 2 Centro, 3 Sur)'
    \quit
\endif
SELECT (:'region' IN ('1', '2', '3')) AS region_valida \gset
\if :region_valida
\else
    \echo 'ERROR: la región debe ser 1 (Norte), 2 (Centro) o 3 (Sur)'
    \quit
\endif

BEGIN;
SET search_path TO app;

-- =====================================================================
-- 1. Fecha de la reserva en el directorio (cambio a A3 previsto en D-01)
-- =====================================================================
ALTER TABLE directorio_correo
    ADD COLUMN IF NOT EXISTS fecha_reserva timestamptz NOT NULL DEFAULT now();

-- =====================================================================
-- 2. Directorio de fragmentos: la topología del anillo
--    Norte -> Centro -> Sur -> Norte: la copia de cada región vive en el
--    nodo siguiente. Es la topología FIJA del diseño; qué nodo está
--    activo en un momento dado lo decide la API (D-01 §8).
--    Es una tabla global: la escribe el nodo escritor y se replica (A11).
-- =====================================================================
CREATE TABLE IF NOT EXISTS fragmento (
    region_id      smallint     PRIMARY KEY REFERENCES region (region_id),
    nodo_primario  varchar(20)  NOT NULL UNIQUE,
    nodo_copia     varchar(20)  NOT NULL UNIQUE,
    CONSTRAINT ck_fragmento_distintos CHECK (nodo_primario <> nodo_copia),
    CONSTRAINT ck_fragmento_nodos CHECK (
        nodo_primario IN ('norte', 'centro', 'sur') AND nodo_copia IN ('norte', 'centro', 'sur'))
);

INSERT INTO fragmento (region_id, nodo_primario, nodo_copia) VALUES
    (1, 'norte',  'centro'),
    (2, 'centro', 'sur'),
    (3, 'sur',    'norte')
ON CONFLICT (region_id) DO UPDATE
    SET nodo_primario = EXCLUDED.nodo_primario,
        nodo_copia    = EXCLUDED.nodo_copia;

COMMENT ON TABLE fragmento IS
    'A9: topología del anillo (D-01 §3). Primario y copia de cada región. El nodo activo lo decide la API.';

-- =====================================================================
-- 3. Región local de este nodo
--    Se guarda en la base: aplica a TODAS las conexiones nuevas.
--    Después de una promoción, promover.sh (A12) la cambia a una lista,
--    por ejemplo '2,1'.
-- =====================================================================
SELECT format('ALTER DATABASE %I SET app.region_local = %L', current_database(), :'region') \gexec
-- Y para el resto de este script (la sesión actual no ve el ALTER DATABASE):
SELECT set_config('app.region_local', :'region', true);

-- =====================================================================
-- 4. fn_region_local(): regiones que atiende este nodo, como arreglo.
--    Si no está configurado devuelve un arreglo vacío (nunca NULL), así
--    las comparaciones con ANY() simplemente no coinciden.
-- =====================================================================
CREATE OR REPLACE FUNCTION fn_region_local()
RETURNS smallint[]
LANGUAGE sql
STABLE
AS $$
    SELECT COALESCE(
        string_to_array(NULLIF(current_setting('app.region_local', true), ''), ',')::smallint[],
        '{}'::smallint[]);
$$;

COMMENT ON FUNCTION fn_region_local() IS
    'A9: regiones que atiende este nodo (app.region_local), p. ej. {2} o {2,1} tras una promoción';

-- =====================================================================
-- 5. fn_ubicar_usuario(): el directorio, como lo usa la API al hacer login.
--    Recibe el HMAC del correo (lo calcula la API) y devuelve la región
--    y el usuario_id. Sin filas = el correo no está registrado.
-- =====================================================================
CREATE OR REPLACE FUNCTION fn_ubicar_usuario(p_correo_hmac varchar)
RETURNS TABLE (region_id smallint, usuario_id uuid)
LANGUAGE sql
STABLE
AS $$
    SELECT d.region_id, d.usuario_id
    FROM directorio_correo d
    WHERE d.correo_hmac = p_correo_hmac;
$$;

COMMENT ON FUNCTION fn_ubicar_usuario(varchar) IS
    'A9: devuelve región y usuario_id de un correo (por su HMAC). La API lo usa al iniciar sesión';

-- =====================================================================
-- 6. Revisión de huérfanas (D-01 §6). Solo DETECTAN: las reservas se
--    borran en el nodo escritor de las globales, nunca en una copia.
-- =====================================================================
-- Reserva de una región de este nodo, con más de 10 minutos, sin usuario.
CREATE OR REPLACE VIEW vw_reservas_huerfanas AS
SELECT d.correo_hmac, d.region_id, d.usuario_id, d.fecha_reserva
FROM directorio_correo d
WHERE d.region_id = ANY (fn_region_local())
  AND d.fecha_reserva < now() - interval '10 minutes'
  AND NOT EXISTS (SELECT 1 FROM usuario u
                  WHERE u.region_id = d.region_id AND u.usuario_id = d.usuario_id);

-- Usuario de este nodo sin fila en el directorio (no debería pasar: se
-- revisa a mano).
CREATE OR REPLACE VIEW vw_usuarios_sin_directorio AS
SELECT u.region_id, u.usuario_id, u.fecha_registro
FROM usuario u
WHERE u.region_id = ANY (fn_region_local())
  AND NOT EXISTS (SELECT 1 FROM directorio_correo d
                  WHERE d.usuario_id = u.usuario_id);

-- =====================================================================
-- 7. Dueño y permisos (mismo modelo que A7)
-- =====================================================================
ALTER TABLE fragmento OWNER TO plantas_owner;
ALTER FUNCTION fn_region_local() OWNER TO plantas_owner;
ALTER FUNCTION fn_ubicar_usuario(varchar) OWNER TO plantas_owner;
ALTER VIEW vw_reservas_huerfanas OWNER TO plantas_owner;
ALTER VIEW vw_usuarios_sin_directorio OWNER TO plantas_owner;

REVOKE ALL ON fragmento, vw_reservas_huerfanas, vw_usuarios_sin_directorio
    FROM PUBLIC, plantas_app, plantas_lectura;
REVOKE ALL ON FUNCTION fn_region_local(), fn_ubicar_usuario(varchar) FROM PUBLIC;

-- La API lee la topología, ubica usuarios y conoce la región local.
GRANT SELECT ON fragmento TO plantas_app, plantas_lectura;
GRANT EXECUTE ON FUNCTION fn_region_local()           TO plantas_app, plantas_lectura;
GRANT EXECUTE ON FUNCTION fn_ubicar_usuario(varchar)  TO plantas_app;
-- Las vistas de huérfanas son de administración (plantas_admin las ve
-- por ser miembro de plantas_owner); la API no las necesita.

COMMIT;

\echo 'Fragmentación de A9 configurada. Región de este nodo:' :region
