-- =====================================================================
-- A11 · Quitar la replicación de este nodo (antes de reinstalar)
-- PostgreSQL 16
-- Responsable: Alexa Yalee Sánchez Tejeda
-- IA: generado y revisado (Claude) — ver docs/bitacora-ia.md
--
-- Se corre EN CADA NODO antes de volver a correr 01_esquema.sql, y se
-- pasa DOS VECES por los 3 nodos (iniciar_lab.ps1 lo hace solo):
--   1.a vuelta: cada nodo suelta sus suscripciones sin tocar a los demás.
--   2.a vuelta: cada nodo borra los slots que ya nadie usa.
-- Si no se hace, 01 borra tablas que siguen suscritas y los slots viejos
-- acumulan WAL hasta llenar el disco.
--   psql -U postgres -d plantas -f db/00_limpiar_replicacion.sql
-- No hace nada si el nodo es nuevo.
-- =====================================================================

-- Suscripciones de esta base. Se desactivan y se desligan de su slot
-- remoto antes de borrarlas, así funciona aunque el otro nodo esté apagado
-- (el slot remoto lo borra la 2.a vuelta en ese nodo).
SELECT format('ALTER SUBSCRIPTION %I DISABLE', subname)
FROM pg_subscription
WHERE subdbid = (SELECT oid FROM pg_database WHERE datname = current_database()) \gexec
SELECT format('ALTER SUBSCRIPTION %I SET (slot_name = NONE)', subname)
FROM pg_subscription
WHERE subdbid = (SELECT oid FROM pg_database WHERE datname = current_database()) \gexec
SELECT format('DROP SUBSCRIPTION %I', subname)
FROM pg_subscription
WHERE subdbid = (SELECT oid FROM pg_database WHERE datname = current_database()) \gexec

-- Publicaciones.
DROP PUBLICATION IF EXISTS pub_frag;
DROP PUBLICATION IF EXISTS pub_fijos;
DROP PUBLICATION IF EXISTS pub_globales;

-- Slots que ya nadie usa (sus suscripciones se soltaron en la 1.a vuelta).
SELECT count(pg_drop_replication_slot(slot_name)) AS slots_borrados
FROM pg_replication_slots
WHERE NOT active AND slot_type = 'logical' AND database = current_database();

\echo 'Replicación de este nodo limpia.'
