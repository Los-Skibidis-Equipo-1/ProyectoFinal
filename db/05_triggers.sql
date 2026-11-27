-- =====================================================================
-- A6 · Triggers
-- PostgreSQL 16
-- Responsable: Alexa Yalee Sánchez Tejeda
-- IA: generado y revisado (Claude) — ver docs/bitacora-ia.md
--
-- 1. Fecha de actualización automática  (usuario, planta, especie)
-- 2. Alertas por humedad                (planta -> alerta)
-- 3. Auditoría de cambios               (usuario, planta, especie -> auditoria)
--
-- Notas:
--  * En una tabla particionada, el trigger se crea una vez en la tabla
--    padre y PostgreSQL lo aplica a cada partición.
--  * Orden en un UPDATE: primero el trigger BEFORE (pone la fecha),
--    luego se guarda la fila y al final los AFTER (alerta y auditoría),
--    que ya ven la fila definitiva.
--
-- Cómo correrlo (después de 01 a 04):
--   psql -U postgres -d plantas -f db/05_triggers.sql
-- Se puede correr varias veces (CREATE OR REPLACE / DROP TRIGGER IF EXISTS).
-- =====================================================================

\set ON_ERROR_STOP on

BEGIN;
SET search_path TO app;

-- =====================================================================
-- 1. FECHA DE ACTUALIZACIÓN
-- Antes de guardar cualquier UPDATE pone fecha_actualizacion = now().
-- Así la API no tiene que acordarse de hacerlo, y nadie puede poner
-- una fecha falsa.
-- =====================================================================
CREATE OR REPLACE FUNCTION trg_fecha_actualizacion()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.fecha_actualizacion := now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS tg_usuario_fecha_actualizacion ON usuario;
CREATE TRIGGER tg_usuario_fecha_actualizacion
    BEFORE UPDATE ON usuario
    FOR EACH ROW EXECUTE FUNCTION trg_fecha_actualizacion();

DROP TRIGGER IF EXISTS tg_planta_fecha_actualizacion ON planta;
CREATE TRIGGER tg_planta_fecha_actualizacion
    BEFORE UPDATE ON planta
    FOR EACH ROW EXECUTE FUNCTION trg_fecha_actualizacion();

DROP TRIGGER IF EXISTS tg_especie_fecha_actualizacion ON especie;
CREATE TRIGGER tg_especie_fecha_actualizacion
    BEFORE UPDATE ON especie
    FOR EACH ROW EXECUTE FUNCTION trg_fecha_actualizacion();

-- =====================================================================
-- 2. ALERTAS POR HUMEDAD
-- Se dispara cuando la API actualiza planta.humedad_actual (después de
-- guardar una lectura en MongoDB). Usa fn_estado_hidratacion de A5.
--   * baja o alta -> crea UNA alerta pendiente de ese tipo (si ya hay
--                    una pendiente, no la repite).
--   * cualquier estado -> da por atendidas las alertas de humedad que ya
--                    no corresponden (por ejemplo, la humedad volvió a
--                    la normalidad, o pasó de baja a alta).
--   * Solo para plantas activas.
-- No hay riesgo de alertas duplicadas por dos lecturas simultáneas:
-- el UPDATE de la planta bloquea su fila hasta terminar la transacción.
-- =====================================================================
CREATE OR REPLACE FUNCTION trg_alerta_humedad()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_min    numeric;
    v_max    numeric;
    v_estado text;
    v_tipo   text;   -- tipo de alerta que corresponde ahora (o NULL)
BEGIN
    IF NEW.estatus <> 'activa' THEN
        RETURN NULL;
    END IF;

    SELECT humedad_ideal_min, humedad_ideal_max
      INTO v_min, v_max
    FROM especie
    WHERE especie_id = NEW.especie_id;

    v_estado := fn_estado_hidratacion(NEW.humedad_actual, v_min, v_max);
    v_tipo := CASE v_estado
                  WHEN 'baja' THEN 'humedad_baja'
                  WHEN 'alta' THEN 'humedad_alta'
              END;

    -- Atender las alertas de humedad que ya no corresponden.
    UPDATE alerta
    SET estado = 'atendida',
        fecha_atendida = GREATEST(now(), fecha_generada)
    WHERE region_id = NEW.region_id
      AND planta_id = NEW.planta_id
      AND estado = 'pendiente'
      AND tipo IN ('humedad_baja', 'humedad_alta')
      AND tipo IS DISTINCT FROM v_tipo;

    -- Crear la alerta nueva si hace falta y no hay una igual pendiente.
    IF v_tipo IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM alerta
        WHERE region_id = NEW.region_id
          AND planta_id = NEW.planta_id
          AND tipo = v_tipo
          AND estado = 'pendiente'
    ) THEN
        INSERT INTO alerta (region_id, planta_id, tipo, mensaje)
        VALUES (NEW.region_id, NEW.planta_id, v_tipo,
                format('%s: humedad %s %% (ideal entre %s y %s %%)',
                       NEW.apodo, NEW.humedad_actual, v_min, v_max));
    END IF;

    RETURN NULL;   -- en un trigger AFTER el valor de retorno se ignora
END;
$$;

DROP TRIGGER IF EXISTS tg_planta_alerta_humedad ON planta;
CREATE TRIGGER tg_planta_alerta_humedad
    AFTER UPDATE OF humedad_actual ON planta
    FOR EACH ROW
    WHEN (NEW.humedad_actual IS DISTINCT FROM OLD.humedad_actual)
    EXECUTE FUNCTION trg_alerta_humedad();

-- =====================================================================
-- 3. AUDITORÍA
-- Guarda en auditoria cada INSERT, UPDATE y DELETE de las tablas con
-- datos personales o administrativos.
--   * Argumento 1: nombre de la tabla. Se pasa a mano porque en una
--     tabla particionada TG_TABLE_NAME da el nombre de la partición
--     (usuario_r2), no el de la tabla (usuario).
--   * Argumento 2: nombre de la columna id de la tabla.
--   * Argumentos 3 en adelante: columnas que, si son las ÚNICAS que
--     cambiaron, NO se auditan. En planta son las que la API actualiza
--     con cada lectura (cada 15 min): auditarlas llenaría la tabla con
--     millones de filas sin valor.
--   * Nunca copia password_hash a la auditoría.
--   * usuario_app sale de SET app.usuario_id = '<uuid>' que hace la API.
-- SECURITY DEFINER: la función corre con los permisos de su dueño, así
-- la cuenta de servicio de la API no necesita permiso de escribir en
-- auditoria y no puede falsificar registros (se completa en A7).
-- =====================================================================
CREATE OR REPLACE FUNCTION trg_auditoria()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = app, pg_temp
AS $$
DECLARE
    v_tabla    text := TG_ARGV[0];
    v_col_id   text := TG_ARGV[1];
    v_ignorar  text[] := TG_ARGV[2:];
    v_anterior jsonb;
    v_nuevo    jsonb;
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        v_anterior := to_jsonb(OLD) - 'password_hash';
    END IF;
    IF TG_OP IN ('INSERT', 'UPDATE') THEN
        v_nuevo := to_jsonb(NEW) - 'password_hash';
    END IF;

    -- UPDATE que solo tocó columnas ignoradas (y la fecha de actualización): no se audita.
    IF TG_OP = 'UPDATE'
       AND (v_anterior - v_ignorar - 'fecha_actualizacion')
         = (v_nuevo    - v_ignorar - 'fecha_actualizacion') THEN
        RETURN NULL;
    END IF;

    INSERT INTO auditoria (tabla, operacion, registro_id, usuario_app,
                           datos_anteriores, datos_nuevos)
    VALUES (v_tabla, TG_OP,
            COALESCE(v_nuevo, v_anterior) ->> v_col_id,
            NULLIF(current_setting('app.usuario_id', true), ''),
            v_anterior, v_nuevo);

    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS tg_usuario_auditoria ON usuario;
CREATE TRIGGER tg_usuario_auditoria
    AFTER INSERT OR UPDATE OR DELETE ON usuario
    FOR EACH ROW EXECUTE FUNCTION trg_auditoria('usuario', 'usuario_id');

DROP TRIGGER IF EXISTS tg_planta_auditoria ON planta;
CREATE TRIGGER tg_planta_auditoria
    AFTER INSERT OR UPDATE OR DELETE ON planta
    FOR EACH ROW EXECUTE FUNCTION trg_auditoria('planta', 'planta_id', 'humedad_actual', 'fecha_ultima_lectura');

DROP TRIGGER IF EXISTS tg_especie_auditoria ON especie;
CREATE TRIGGER tg_especie_auditoria
    AFTER INSERT OR UPDATE OR DELETE ON especie
    FOR EACH ROW EXECUTE FUNCTION trg_auditoria('especie', 'especie_id');

COMMIT;

\echo 'Triggers de A6 creados correctamente.'
