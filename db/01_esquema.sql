-- =====================================================================
-- A3 · Esquema SQL — Sistema de cuidado de plantas (Los Skibidis)
-- PostgreSQL 16
-- Responsable: Alexa Yalee Sánchez Tejeda
-- IA: generado y revisado (Claude) — ver docs/bitacora-ia.md
--
-- Qué hace este script:
--   1. Borra y vuelve a crear el esquema "app" (se puede correr las veces que sea).
--   2. Crea las tablas GLOBALES (se replican completas en los 3 nodos):
--        region, estado, especie, directorio_correo
--   3. Crea las tablas FRAGMENTADAS por region_id (PARTITION BY LIST):
--        usuario, planta, sensor, cuidado, alerta
--      y sus 3 particiones locales (1 Norte, 2 Centro, 3 Sur).
--      En A9 cada nodo se quedará solo con la partición de su región.
--   4. Crea la tabla LOCAL de auditoría (cada nodo tiene la suya, no se replica).
--
-- Qué NO hace (va en otras tareas):
--   índices extra (A4), procedimientos y funciones (A5), triggers (A6),
--   roles y vistas (A7), distribución entre nodos (A9).
--
-- Cómo correrlo:
--   psql -U postgres -d plantas -f db/01_esquema.sql
-- =====================================================================

\set ON_ERROR_STOP on

BEGIN;

DROP SCHEMA IF EXISTS app CASCADE;
CREATE SCHEMA app;
SET search_path TO app;

-- =====================================================================
-- 1. TABLAS GLOBALES (replicadas completas en todos los nodos)
-- =====================================================================

-- ---------------------------------------------------------------------
-- region: las 3 regiones del país. Solo existen los valores 1, 2 y 3.
-- ---------------------------------------------------------------------
CREATE TABLE region (
    region_id  smallint    PRIMARY KEY,
    nombre     varchar(20) NOT NULL UNIQUE,
    CONSTRAINT ck_region_id CHECK (region_id BETWEEN 1 AND 3)
);

-- ---------------------------------------------------------------------
-- estado: las 32 entidades federativas y la región a la que pertenecen.
-- La región se guarda como DATO (no fija en código) porque la opción B
-- de fragmentación todavía se confirma con la medición de A13.
-- El UNIQUE (region_id, estado_id) permite que usuario use una llave
-- foránea compuesta y así un usuario NUNCA quede en una región distinta
-- a la de su estado.
-- ---------------------------------------------------------------------
CREATE TABLE estado (
    estado_id        smallint     PRIMARY KEY,
    nombre           varchar(40)  NOT NULL UNIQUE,
    region_id        smallint     NOT NULL REFERENCES region (region_id),
    poblacion_aprox  integer      NOT NULL,
    CONSTRAINT ck_estado_id        CHECK (estado_id BETWEEN 1 AND 32),
    CONSTRAINT ck_estado_poblacion CHECK (poblacion_aprox > 0),
    CONSTRAINT uq_estado_region    UNIQUE (region_id, estado_id)
);

-- ---------------------------------------------------------------------
-- especie: catálogo de especies (A20). "fuente" es obligatoria.
-- humedad en porcentaje (0 a 100) y temperatura en grados Celsius.
-- ---------------------------------------------------------------------
CREATE TABLE especie (
    especie_id             integer       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre_comun           varchar(80)   NOT NULL,
    nombre_cientifico      varchar(120)  NOT NULL UNIQUE,
    humedad_ideal_min      numeric(5,2)  NOT NULL,
    humedad_ideal_max      numeric(5,2)  NOT NULL,
    frecuencia_riego_dias  smallint      NOT NULL,
    luz                    varchar(10)   NOT NULL,
    temp_min               numeric(4,1)  NOT NULL,
    temp_max               numeric(4,1)  NOT NULL,
    cuidados               text,
    fuente                 text          NOT NULL,
    fecha_actualizacion    timestamptz   NOT NULL DEFAULT now(),
    CONSTRAINT ck_especie_humedad_rango CHECK (humedad_ideal_min >= 0 AND humedad_ideal_max <= 100),
    CONSTRAINT ck_especie_humedad_orden CHECK (humedad_ideal_min < humedad_ideal_max),
    CONSTRAINT ck_especie_temp_orden    CHECK (temp_min < temp_max),
    CONSTRAINT ck_especie_temp_rango    CHECK (temp_min >= -20 AND temp_max <= 60),
    CONSTRAINT ck_especie_riego         CHECK (frecuencia_riego_dias BETWEEN 1 AND 365),
    CONSTRAINT ck_especie_luz           CHECK (luz IN ('sombra', 'indirecta', 'directa')),
    CONSTRAINT ck_especie_fuente        CHECK (length(trim(fuente)) > 0)
);

-- ---------------------------------------------------------------------
-- directorio_correo: dice en qué región vive cada usuario.
-- correo_hmac = HMAC-SHA256 del correo normalizado (minúsculas y sin
-- espacios) con una llave secreta que NO va en el repo. Se guarda en
-- hexadecimal (64 caracteres). Garantiza que un correo exista una sola
-- vez en TODO el país (en la tabla usuario solo es único por región).
-- Es varchar y no char: con char(64) PostgreSQL convierte la columna al
-- comparar contra un texto y deja de usar el índice de la llave (lo vimos
-- en el EXPLAIN de A4).
-- No lleva llave foránea a usuario porque usuario está fragmentado
-- (en un nodo no existen los usuarios de las otras regiones).
-- ---------------------------------------------------------------------
CREATE TABLE directorio_correo (
    correo_hmac  varchar(64) PRIMARY KEY,
    region_id    smallint   NOT NULL REFERENCES region (region_id),
    usuario_id   uuid       NOT NULL UNIQUE,
    CONSTRAINT ck_directorio_hex CHECK (correo_hmac ~ '^[0-9a-f]{64}$')
);

-- =====================================================================
-- 2. TABLAS FRAGMENTADAS por region_id
--    Regla de PostgreSQL: en una tabla particionada, la PRIMARY KEY y
--    todo UNIQUE deben incluir la columna de partición (region_id).
--    Por eso todas las llaves son compuestas (region_id, ..._id).
--    Los id son UUID para que no choquen entre nodos.
-- =====================================================================

-- ---------------------------------------------------------------------
-- usuario: la tabla con más datos personales.
-- ---------------------------------------------------------------------
CREATE TABLE usuario (
    region_id            smallint      NOT NULL,
    usuario_id           uuid          NOT NULL DEFAULT gen_random_uuid(),
    nombre               varchar(80)   NOT NULL,
    apellidos            varchar(120)  NOT NULL,
    correo               varchar(254)  NOT NULL,
    password_hash        text          NOT NULL,
    rol                  varchar(10)   NOT NULL DEFAULT 'usuario',
    estado_id            smallint      NOT NULL,
    activo               boolean       NOT NULL DEFAULT true,
    fecha_registro       timestamptz   NOT NULL DEFAULT now(),
    fecha_actualizacion  timestamptz   NOT NULL DEFAULT now(),
    CONSTRAINT pk_usuario PRIMARY KEY (region_id, usuario_id),
    CONSTRAINT uq_usuario_correo UNIQUE (region_id, correo),
    -- El estado del usuario debe pertenecer a la misma región que la fila.
    CONSTRAINT fk_usuario_estado FOREIGN KEY (region_id, estado_id)
        REFERENCES estado (region_id, estado_id),
    CONSTRAINT ck_usuario_rol    CHECK (rol IN ('usuario', 'admin')),
    -- El correo se guarda ya normalizado: en minúsculas y sin espacios.
    CONSTRAINT ck_usuario_correo CHECK (
        correo = lower(trim(correo))
        AND correo ~ '^[^@\s]+@[^@\s]+\.[^@\s]+$'
    ),
    -- scrypt guarda parámetros + sal + hash; nunca debe ser corto.
    CONSTRAINT ck_usuario_password CHECK (length(password_hash) >= 32),
    CONSTRAINT ck_usuario_fechas   CHECK (fecha_actualizacion >= fecha_registro)
) PARTITION BY LIST (region_id);

CREATE TABLE usuario_r1 PARTITION OF usuario FOR VALUES IN (1);  -- Norte
CREATE TABLE usuario_r2 PARTITION OF usuario FOR VALUES IN (2);  -- Centro
CREATE TABLE usuario_r3 PARTITION OF usuario FOR VALUES IN (3);  -- Sur

-- ---------------------------------------------------------------------
-- planta: pertenece a un usuario (misma región) y a una especie.
-- humedad_actual y fecha_ultima_lectura las actualiza la API cada vez
-- que guarda una lectura en MongoDB; sobre ese UPDATE se dispara el
-- trigger de alertas de A6 y se resuelve la consulta Q10.
-- ---------------------------------------------------------------------
CREATE TABLE planta (
    region_id              smallint      NOT NULL,
    planta_id              uuid          NOT NULL DEFAULT gen_random_uuid(),
    usuario_id             uuid          NOT NULL,
    especie_id             integer       NOT NULL,
    apodo                  varchar(60)   NOT NULL,
    tipo_espacio           varchar(15)   NOT NULL,
    ubicacion_descripcion  varchar(100),
    fecha_adquisicion      date,
    estatus                varchar(10)   NOT NULL DEFAULT 'activa',
    humedad_actual         numeric(5,2),
    fecha_ultima_lectura   timestamptz,
    fecha_registro         timestamptz   NOT NULL DEFAULT now(),
    fecha_actualizacion    timestamptz   NOT NULL DEFAULT now(),
    CONSTRAINT pk_planta PRIMARY KEY (region_id, planta_id),
    -- Llave compuesta: la planta queda en la MISMA región que su dueño.
    -- Si se borra el usuario, se borran sus plantas.
    CONSTRAINT fk_planta_usuario FOREIGN KEY (region_id, usuario_id)
        REFERENCES usuario (region_id, usuario_id) ON DELETE CASCADE,
    -- No se puede borrar una especie que tenga plantas.
    CONSTRAINT fk_planta_especie FOREIGN KEY (especie_id)
        REFERENCES especie (especie_id) ON DELETE RESTRICT,
    CONSTRAINT ck_planta_espacio CHECK (tipo_espacio IN ('casa', 'departamento', 'oficina', 'patio')),
    CONSTRAINT ck_planta_estatus CHECK (estatus IN ('activa', 'fallecida', 'regalada')),
    CONSTRAINT ck_planta_humedad CHECK (humedad_actual IS NULL OR humedad_actual BETWEEN 0 AND 100),
    -- Si hay humedad actual, debe saberse cuándo se leyó (y al revés).
    CONSTRAINT ck_planta_lectura CHECK ((humedad_actual IS NULL) = (fecha_ultima_lectura IS NULL)),
    CONSTRAINT ck_planta_apodo   CHECK (length(trim(apodo)) > 0)
) PARTITION BY LIST (region_id);

CREATE TABLE planta_r1 PARTITION OF planta FOR VALUES IN (1);
CREATE TABLE planta_r2 PARTITION OF planta FOR VALUES IN (2);
CREATE TABLE planta_r3 PARTITION OF planta FOR VALUES IN (3);

-- ---------------------------------------------------------------------
-- sensor: dispositivo (simulado o ESP32) conectado a una planta.
-- Sus lecturas viven en MongoDB y apuntan a sensor_id.
-- ---------------------------------------------------------------------
CREATE TABLE sensor (
    region_id                  smallint     NOT NULL,
    sensor_id                  uuid         NOT NULL DEFAULT gen_random_uuid(),
    planta_id                  uuid         NOT NULL,
    tipo                       varchar(10)  NOT NULL,
    identificador_dispositivo  varchar(64),
    es_simulado                boolean      NOT NULL DEFAULT true,
    activo                     boolean      NOT NULL DEFAULT true,
    fecha_instalacion          timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT pk_sensor PRIMARY KEY (region_id, sensor_id),
    CONSTRAINT fk_sensor_planta FOREIGN KEY (region_id, planta_id)
        REFERENCES planta (region_id, planta_id) ON DELETE CASCADE,
    -- Un ESP32 físico (MAC o número de serie) no se registra dos veces.
    CONSTRAINT uq_sensor_dispositivo UNIQUE (region_id, identificador_dispositivo),
    CONSTRAINT ck_sensor_tipo CHECK (tipo IN ('humedad', 'ambiente')),
    -- Un sensor real (no simulado) debe traer su identificador.
    CONSTRAINT ck_sensor_real CHECK (es_simulado OR identificador_dispositivo IS NOT NULL)
) PARTITION BY LIST (region_id);

CREATE TABLE sensor_r1 PARTITION OF sensor FOR VALUES IN (1);
CREATE TABLE sensor_r2 PARTITION OF sensor FOR VALUES IN (2);
CREATE TABLE sensor_r3 PARTITION OF sensor FOR VALUES IN (3);

-- ---------------------------------------------------------------------
-- cuidado: riego, fertilizado, poda, trasplante u otro.
-- cantidad_ml solo tiene sentido en un riego.
-- ---------------------------------------------------------------------
CREATE TABLE cuidado (
    region_id    smallint      NOT NULL,
    cuidado_id   uuid          NOT NULL DEFAULT gen_random_uuid(),
    planta_id    uuid          NOT NULL,
    tipo         varchar(12)   NOT NULL,
    fecha_hora   timestamptz   NOT NULL DEFAULT now(),
    cantidad_ml  integer,
    notas        varchar(500),
    CONSTRAINT pk_cuidado PRIMARY KEY (region_id, cuidado_id),
    CONSTRAINT fk_cuidado_planta FOREIGN KEY (region_id, planta_id)
        REFERENCES planta (region_id, planta_id) ON DELETE CASCADE,
    CONSTRAINT ck_cuidado_tipo CHECK (tipo IN ('riego', 'fertilizado', 'poda', 'trasplante', 'otro')),
    CONSTRAINT ck_cuidado_cantidad CHECK (
        (tipo = 'riego'  AND (cantidad_ml IS NULL OR cantidad_ml BETWEEN 1 AND 20000))
        OR (tipo <> 'riego' AND cantidad_ml IS NULL)
    )
) PARTITION BY LIST (region_id);

CREATE TABLE cuidado_r1 PARTITION OF cuidado FOR VALUES IN (1);
CREATE TABLE cuidado_r2 PARTITION OF cuidado FOR VALUES IN (2);
CREATE TABLE cuidado_r3 PARTITION OF cuidado FOR VALUES IN (3);

-- ---------------------------------------------------------------------
-- alerta: alertas y recordatorios en una sola tabla (las genera A6).
-- Si está atendida debe tener fecha de atención, y si está pendiente no.
-- ---------------------------------------------------------------------
CREATE TABLE alerta (
    region_id       smallint      NOT NULL,
    alerta_id       uuid          NOT NULL DEFAULT gen_random_uuid(),
    planta_id       uuid          NOT NULL,
    tipo            varchar(16)   NOT NULL,
    mensaje         varchar(300)  NOT NULL,
    fecha_generada  timestamptz   NOT NULL DEFAULT now(),
    estado          varchar(10)   NOT NULL DEFAULT 'pendiente',
    fecha_atendida  timestamptz,
    CONSTRAINT pk_alerta PRIMARY KEY (region_id, alerta_id),
    CONSTRAINT fk_alerta_planta FOREIGN KEY (region_id, planta_id)
        REFERENCES planta (region_id, planta_id) ON DELETE CASCADE,
    CONSTRAINT ck_alerta_tipo CHECK (tipo IN ('humedad_baja', 'humedad_alta', 'riego_pendiente', 'temperatura')),
    CONSTRAINT ck_alerta_estado CHECK (estado IN ('pendiente', 'atendida')),
    CONSTRAINT ck_alerta_atencion CHECK (
        (estado = 'pendiente' AND fecha_atendida IS NULL)
        OR (estado = 'atendida' AND fecha_atendida IS NOT NULL AND fecha_atendida >= fecha_generada)
    )
) PARTITION BY LIST (region_id);

CREATE TABLE alerta_r1 PARTITION OF alerta FOR VALUES IN (1);
CREATE TABLE alerta_r2 PARTITION OF alerta FOR VALUES IN (2);
CREATE TABLE alerta_r3 PARTITION OF alerta FOR VALUES IN (3);

-- =====================================================================
-- 3. TABLA LOCAL (cada nodo tiene la suya; NO se replica porque
--    datos_anteriores/datos_nuevos pueden traer datos personales)
-- =====================================================================

-- ---------------------------------------------------------------------
-- auditoria: la llena el trigger de A6.
-- usuario_db  = cuenta de PostgreSQL (casi siempre la cuenta de servicio).
-- usuario_app = usuario de la app; la API lo manda con
--               SET app.usuario_id = '<uuid>' antes de cada operación.
-- ---------------------------------------------------------------------
CREATE TABLE auditoria (
    auditoria_id      bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tabla             varchar(40)  NOT NULL,
    operacion         varchar(6)   NOT NULL,
    registro_id       text         NOT NULL,
    usuario_db        text         NOT NULL DEFAULT current_user,
    usuario_app       text,
    fecha_hora        timestamptz  NOT NULL DEFAULT now(),
    datos_anteriores  jsonb,
    datos_nuevos      jsonb,
    CONSTRAINT ck_auditoria_operacion CHECK (operacion IN ('INSERT', 'UPDATE', 'DELETE')),
    -- INSERT no tiene datos anteriores; DELETE no tiene datos nuevos.
    CONSTRAINT ck_auditoria_datos CHECK (
        (operacion = 'INSERT' AND datos_anteriores IS NULL     AND datos_nuevos IS NOT NULL)
        OR (operacion = 'UPDATE' AND datos_anteriores IS NOT NULL AND datos_nuevos IS NOT NULL)
        OR (operacion = 'DELETE' AND datos_anteriores IS NOT NULL AND datos_nuevos IS NULL)
    )
);

COMMIT;

\echo 'Esquema app creado correctamente.'
