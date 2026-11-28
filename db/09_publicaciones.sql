-- =====================================================================
-- A11 (2 de 3) · Publicaciones (lo que cada nodo ofrece para replicar)
-- PostgreSQL 16 · D-01 §3 y §4
-- Responsable: Alexa Yalee Sánchez Tejeda
-- IA: generado y revisado (Claude) — ver docs/bitacora-ia.md
--
-- Se corre EN CADA NODO, después de 08 y ANTES de 10 en cualquier nodo:
--   psql -U postgres -d plantas -v escritor=norte -f db/09_publicaciones.sql
--
--   pub_frag      (todos)        las 5 particiones de SU región -> su copia en el anillo
--   pub_fijos     (solo escritor) region, estado, fragmento     -> los otros dos nodos
--   pub_globales  (solo escritor) especie, directorio_correo    -> los otros dos nodos
--
-- Se publican las PARTICIONES (usuario_r1, ...), no las tablas padre: así
-- solo viaja la región de este nodo. auditoria no se publica (es local).
-- =====================================================================

\set ON_ERROR_STOP on

\if :{?escritor}
\else
    \echo 'ERROR: falta -v escritor=<norte|centro|sur>'
    \quit
\endif

SELECT f.nodo_primario AS nodo_local, f.region_id AS region_local
FROM app.fragmento f
WHERE f.region_id = (app.fn_region_local())[1] \gset
SELECT (:'nodo_local' = :'escritor') AS es_escritor \gset

DROP PUBLICATION IF EXISTS pub_frag;
DROP PUBLICATION IF EXISTS pub_fijos;
DROP PUBLICATION IF EXISTS pub_globales;

-- Fragmento de la región de este nodo (va a su copia en el anillo).
SELECT format('CREATE PUBLICATION pub_frag FOR TABLE %s',
              string_agg(format('app.%I', t || '_r' || :'region_local'), ', '))
FROM unnest(ARRAY['usuario', 'planta', 'sensor', 'cuidado', 'alerta']) AS t \gexec

\if :es_escritor
    CREATE PUBLICATION pub_fijos    FOR TABLE app.region, app.estado, app.fragmento;
    CREATE PUBLICATION pub_globales FOR TABLE app.especie, app.directorio_correo;
\endif

\echo 'Publicaciones de este nodo:'
SELECT p.pubname AS publicacion, string_agg(t.tablename, ', ' ORDER BY t.tablename) AS tablas
FROM pg_publication p
JOIN pg_publication_tables t ON t.pubname = p.pubname
GROUP BY p.pubname ORDER BY p.pubname;
