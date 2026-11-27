-- =====================================================================
-- A11 (3 de 3) · Suscripciones (lo que cada nodo recibe)
-- PostgreSQL 16 · D-01 §3, §4 y §5
-- Responsable: Alexa Yalee Sánchez Tejeda
-- IA: generado y revisado (Claude) — ver docs/bitacora-ia.md
--
-- Se corre EN CADA NODO, cuando los 3 ya corrieron 09:
--   psql -U postgres -d plantas -v escritor=norte -v pass_replica=... \
--        -v host_norte=pg-norte -v host_centro=pg-centro -v host_sur=pg-sur \
--        -f db/10_suscripciones.sql
-- Opcionales: -v port_norte=5432 (y centro, sur), -v sslmode=prefer
--
-- Las direcciones NO están escritas aquí: en el laboratorio son los
-- nombres de los contenedores y en las 3 computadoras serán las IP de la
-- VPN. Solo cambia lo que se pasa con -v (desde .env).
--
--   sub_frag_r<N>    copia de la región del nodo ANTERIOR del anillo
--                    (Centro copia Norte, Sur copia Centro, Norte copia Sur)
--   sub_fijos_<nodo> region, estado, fragmento   desde el escritor (sin copiar: ya están por 02 y 07)
--   sub_glob_<nodo>  especie, directorio_correo   desde el escritor (copia inicial completa)
--
-- Pensado para una instalación limpia (iniciar_lab.ps1 corre antes 00_limpiar_replicacion.sql).
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
\if :{?sslmode}
\else
    \set sslmode prefer
\endif

-- ¿Quién soy, a quién copio y quién escribe las globales?
SELECT f.nodo_primario AS nodo_local
FROM app.fragmento f WHERE f.region_id = (app.fn_region_local())[1] \gset
SELECT f.nodo_primario AS nodo_anterior, f.region_id AS region_copia
FROM app.fragmento f WHERE f.nodo_copia = :'nodo_local' \gset
SELECT (:'nodo_local' = :'escritor') AS es_escritor \gset

-- Cadena de conexión a cada nodo (la contraseña viaja en la suscripción,
-- que solo puede leer un superusuario).
SELECT format('host=%s port=%s dbname=plantas user=plantas_replica password=%s sslmode=%s',
              CASE n WHEN 'norte' THEN :'host_norte' WHEN 'centro' THEN :'host_centro' ELSE :'host_sur' END,
              CASE n WHEN 'norte' THEN :'port_norte' WHEN 'centro' THEN :'port_centro' ELSE :'port_sur' END,
              :'pass_replica', :'sslmode') AS conn
FROM (VALUES (:'nodo_anterior')) AS v(n) \gset conn_anterior_
SELECT format('host=%s port=%s dbname=plantas user=plantas_replica password=%s sslmode=%s',
              CASE n WHEN 'norte' THEN :'host_norte' WHEN 'centro' THEN :'host_centro' ELSE :'host_sur' END,
              CASE n WHEN 'norte' THEN :'port_norte' WHEN 'centro' THEN :'port_centro' ELSE :'port_sur' END,
              :'pass_replica', :'sslmode') AS conn
FROM (VALUES (:'escritor')) AS v(n) \gset conn_escritor_

-- ---------------------------------------------------------------------
-- 1. Copia del anillo: la región del nodo anterior.
--    La partición copia se vacía antes (D-01 §3: el que regresa se
--    vacía y se vuelve a copiar). TRUNCATE no sirve en una sola
--    partición con llaves foráneas, así que se borra de hijos a padres
--    con session_replication_role = replica: así no se disparan los
--    triggers (no llena la auditoría con el borrado de una copia).
-- ---------------------------------------------------------------------
SELECT format('DROP SUBSCRIPTION IF EXISTS %I', 'sub_frag_r' || :'region_copia') \gexec
SET session_replication_role = replica;
SELECT format('DELETE FROM app.%I', t || '_r' || :'region_copia')
FROM unnest(ARRAY['alerta', 'cuidado', 'sensor', 'planta', 'usuario']) WITH ORDINALITY AS x(t, orden)
ORDER BY orden \gexec
RESET session_replication_role;
SELECT format('CREATE SUBSCRIPTION %I CONNECTION %L PUBLICATION pub_frag WITH (copy_data = true)',
              'sub_frag_r' || :'region_copia', :'conn_anterior_conn') \gexec

-- ---------------------------------------------------------------------
-- 2. Tablas globales (solo si este nodo NO es el escritor).
-- ---------------------------------------------------------------------
\if :es_escritor
    \echo 'Este nodo es el escritor de las globales: no se suscribe a ellas.'
\else
    -- Instalación limpia: especie y directorio deben estar vacíos aquí,
    -- porque llegan completos desde el escritor.
    SELECT (SELECT count(*) FROM app.especie) = 0
       AND (SELECT count(*) FROM app.directorio_correo) = 0 AS globales_vacias \gset
    \if :globales_vacias
    \else
        \echo 'ERROR: especie o directorio_correo ya tienen datos en este nodo; reinstala con iniciar_lab.ps1'
        \quit
    \endif

    SELECT format('DROP SUBSCRIPTION IF EXISTS %I', 'sub_fijos_' || :'nodo_local') \gexec
    SELECT format('DROP SUBSCRIPTION IF EXISTS %I', 'sub_glob_'  || :'nodo_local') \gexec
    SELECT format('CREATE SUBSCRIPTION %I CONNECTION %L PUBLICATION pub_fijos WITH (copy_data = false)',
                  'sub_fijos_' || :'nodo_local', :'conn_escritor_conn') \gexec
    SELECT format('CREATE SUBSCRIPTION %I CONNECTION %L PUBLICATION pub_globales WITH (copy_data = true)',
                  'sub_glob_' || :'nodo_local', :'conn_escritor_conn') \gexec
\endif

\echo 'Suscripciones de este nodo:'
SELECT subname AS suscripcion, subenabled AS activa, array_to_string(subpublications, ', ') AS publicaciones
FROM pg_subscription
WHERE subdbid = (SELECT oid FROM pg_database WHERE datname = current_database())
ORDER BY subname;
