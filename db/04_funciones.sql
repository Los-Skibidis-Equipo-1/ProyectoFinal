-- =====================================================================
-- A5 · Procedimiento almacenado y funciones
-- PostgreSQL 16
-- Responsable: Alexa Yalee Sánchez Tejeda
-- IA: generado y revisado (Claude) — ver docs/bitacora-ia.md
--
-- Contenido:
--   fn_estado_hidratacion(humedad, min, max)  -> 'sin_dato' | 'baja' | 'optima' | 'alta'
--   fn_proximo_riego(region, planta)           -> fecha en que toca el siguiente riego
--   sp_registrar_riego(region, planta, ml, notas, fecha, INOUT cuidado_id)
--       registra el riego y da por atendidas las alertas de riego pendiente
--
-- Errores que lanza el procedimiento (la API de Python los puede distinguir
-- por su SQLSTATE):
--   P0002 no_data_found     -> la planta no existe en esa región
--   23514 check_violation   -> la planta no está activa, cantidad inválida
--                              o fecha en el futuro
--
-- Cómo correrlo (después de 01, 02 y 03):
--   psql -U postgres -d plantas -f db/04_funciones.sql
-- Se puede correr varias veces: usa CREATE OR REPLACE.
-- =====================================================================

\set ON_ERROR_STOP on

BEGIN;
SET search_path TO app;

-- ---------------------------------------------------------------------
-- Función 1 · Estado de hidratación
-- Compara una humedad contra el rango ideal de la especie.
-- Es IMMUTABLE (mismo resultado para los mismos datos, no lee tablas),
-- así que se puede usar en consultas, vistas, índices y en el trigger
-- de alertas de A6.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_estado_hidratacion(
    p_humedad numeric,
    p_min     numeric,
    p_max     numeric
) RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT CASE
        WHEN p_humedad IS NULL OR p_min IS NULL OR p_max IS NULL THEN 'sin_dato'
        WHEN p_humedad < p_min THEN 'baja'
        WHEN p_humedad > p_max THEN 'alta'
        ELSE 'optima'
    END;
$$;

COMMENT ON FUNCTION fn_estado_hidratacion(numeric, numeric, numeric) IS
    'A5: clasifica la humedad (baja, optima, alta, sin_dato) contra el rango ideal de la especie';

-- ---------------------------------------------------------------------
-- Función 2 · Próximo riego
-- Último riego + frecuencia de riego de la especie.
-- Si la planta nunca se ha regado, el riego toca desde que se registró.
-- Devuelve NULL si la planta no existe.
-- Es STABLE (lee tablas, pero no las modifica).
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_proximo_riego(
    p_region_id smallint,
    p_planta_id uuid
) RETURNS timestamptz
LANGUAGE sql
STABLE
AS $$
    SELECT COALESCE(
               (SELECT max(c.fecha_hora)
                FROM cuidado c
                WHERE c.region_id = p.region_id
                  AND c.planta_id = p.planta_id
                  AND c.tipo = 'riego')
               + make_interval(days => e.frecuencia_riego_dias),
               p.fecha_registro)
    FROM planta p
    JOIN especie e ON e.especie_id = p.especie_id
    WHERE p.region_id = p_region_id
      AND p.planta_id = p_planta_id;
$$;

COMMENT ON FUNCTION fn_proximo_riego(smallint, uuid) IS
    'A5: fecha del siguiente riego = último riego + frecuencia de la especie (Q5)';

-- ---------------------------------------------------------------------
-- Procedimiento · Registrar un riego
-- 1. Valida que la planta exista en esa región y esté activa.
-- 2. Valida la cantidad y que la fecha no esté en el futuro.
-- 3. Inserta el cuidado de tipo riego.
-- 4. Da por atendidas las alertas 'riego_pendiente' de esa planta.
-- Todo ocurre dentro de la misma transacción: si algo falla, no se
-- guarda nada.
--
-- Uso:
--   CALL sp_registrar_riego(2::smallint, '<uuid planta>', 250, 'Regué con agua de lluvia');
--   -- el último parámetro (INOUT) regresa el id del cuidado creado
-- ---------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE sp_registrar_riego(
    p_region_id   smallint,
    p_planta_id   uuid,
    p_cantidad_ml integer     DEFAULT NULL,
    p_notas       varchar     DEFAULT NULL,
    p_fecha_hora  timestamptz DEFAULT now(),
    INOUT p_cuidado_id uuid   DEFAULT NULL
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_estatus varchar;
BEGIN
    -- 1. La planta existe y está activa. FOR UPDATE la bloquea mientras
    --    se registra el riego, para que nadie la cambie a la vez.
    SELECT estatus INTO v_estatus
    FROM planta
    WHERE region_id = p_region_id AND planta_id = p_planta_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'La planta % no existe en la región %', p_planta_id, p_region_id
            USING ERRCODE = 'no_data_found';
    END IF;

    IF v_estatus <> 'activa' THEN
        RAISE EXCEPTION 'La planta % no está activa (estatus: %)', p_planta_id, v_estatus
            USING ERRCODE = 'check_violation';
    END IF;

    -- 2. Cantidad y fecha. Se permiten 5 minutos de tolerancia por
    --    diferencias de reloj entre el celular y el servidor.
    IF p_cantidad_ml IS NOT NULL AND p_cantidad_ml <= 0 THEN
        RAISE EXCEPTION 'La cantidad de agua debe ser mayor que 0 (recibido: %)', p_cantidad_ml
            USING ERRCODE = 'check_violation';
    END IF;

    IF p_fecha_hora IS NULL OR p_fecha_hora > now() + interval '5 minutes' THEN
        RAISE EXCEPTION 'La fecha del riego no puede estar vacía ni en el futuro (recibido: %)', p_fecha_hora
            USING ERRCODE = 'check_violation';
    END IF;

    -- 3. Registrar el riego.
    INSERT INTO cuidado (region_id, planta_id, tipo, fecha_hora, cantidad_ml, notas)
    VALUES (p_region_id, p_planta_id, 'riego', p_fecha_hora, p_cantidad_ml, p_notas)
    RETURNING cuidado_id INTO p_cuidado_id;

    -- 4. Atender los recordatorios de riego pendientes de esta planta.
    --    GREATEST evita que fecha_atendida quede antes de fecha_generada
    --    (lo exige el CHECK ck_alerta_atencion).
    UPDATE alerta
    SET estado = 'atendida',
        fecha_atendida = GREATEST(now(), fecha_generada)
    WHERE region_id = p_region_id
      AND planta_id = p_planta_id
      AND tipo = 'riego_pendiente'
      AND estado = 'pendiente';
END;
$$;

COMMENT ON PROCEDURE sp_registrar_riego(smallint, uuid, integer, varchar, timestamptz, uuid) IS
    'A5: registra un riego validando la planta y atiende sus alertas de riego pendiente';

COMMIT;

\echo 'Funciones y procedimiento de A5 creados correctamente.'
