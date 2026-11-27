-- =====================================================================
-- A9 · Pruebas de fragmentación y directorio
-- IA: generado y revisado (Claude) — ver docs/bitacora-ia.md
--
-- Se corre en CADA nodo (después de 01 a 07). Comprueba que:
--   * cada fila cae en el fragmento (partición) de su región;
--   * el anillo de fragmento es correcto;
--   * el nodo conoce su región (app.region_local);
--   * el directorio ubica usuarios y detecta huérfanas.
--   "OK" = esperado. "FALLO" = no (se detiene). Al final: ROLLBACK.
--
-- Cómo correrlo:
--   psql -U postgres -d plantas -f db/tests/a9_pruebas_fragmentacion.sql
-- =====================================================================

\set ON_ERROR_STOP on
\pset tuples_only on

BEGIN;
SET search_path TO app;

-- Región configurada para ESTE nodo (la de ALTER DATABASE), antes de
-- que las pruebas la cambien con SET LOCAL.
SELECT current_setting('app.region_local', true) AS region_nodo \gset
\echo 'Este nodo atiende la región:' :region_nodo

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

CREATE FUNCTION pg_temp.sin_permiso(prueba text, sentencia text)
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    BEGIN
        EXECUTE sentencia;
    EXCEPTION WHEN insufficient_privilege THEN
        RAISE NOTICE 'OK    % (como %)', prueba, current_user;
        RETURN;
    END;
    RAISE EXCEPTION 'FALLO % -> % SÍ pudo hacerlo', prueba, current_user;
END;
$$;
GRANT EXECUTE ON FUNCTION pg_temp.verifica(text, boolean), pg_temp.sin_permiso(text, text) TO PUBLIC;

-- Devuelve el plan de ejecución de una consulta como texto.
CREATE FUNCTION pg_temp.plan(consulta text)
RETURNS text LANGUAGE plpgsql AS $$
DECLARE r text; t text := '';
BEGIN
    FOR r IN EXECUTE 'EXPLAIN (COSTS OFF) ' || consulta LOOP
        t := t || r || E'\n';
    END LOOP;
    RETURN t;
END;
$$;

\echo '--- Configuración del nodo ---'
SELECT pg_temp.verifica('01 este nodo tiene su región configurada (1, 2 o 3)',
       :'region_nodo' IN ('1', '2', '3'));
SELECT pg_temp.verifica('02 la región está guardada en la base (aplica a toda conexión nueva)',
       EXISTS (SELECT 1 FROM pg_db_role_setting s JOIN pg_database d ON d.oid = s.setdatabase
               WHERE d.datname = current_database()
                 AND 'app.region_local=' || :'region_nodo' = ANY (s.setconfig)));

SET LOCAL app.region_local = '2,1';
SELECT pg_temp.verifica('03 fn_region_local lee una lista (como después de una promoción)',
       fn_region_local() = '{2,1}'::smallint[]);
SET LOCAL app.region_local = '';
SELECT pg_temp.verifica('04 sin configurar devuelve un arreglo vacío, no NULL',
       fn_region_local() = '{}'::smallint[]);

\echo '--- Directorio de fragmentos (anillo Norte -> Centro -> Sur -> Norte) ---'
SELECT pg_temp.verifica('05 hay un fragmento por región',
       (SELECT count(*) FROM fragmento) = 3);
SELECT pg_temp.verifica('06 la copia de cada región está en el nodo siguiente del anillo',
       (SELECT array_agg(region_id || ':' || nodo_primario || '>' || nodo_copia ORDER BY region_id)
        FROM fragmento) = '{1:norte>centro,2:centro>sur,3:sur>norte}');
SELECT pg_temp.verifica('07 cada nodo es primario de una región y copia de otra',
       (SELECT count(DISTINCT nodo_primario) = 3 AND count(DISTINCT nodo_copia) = 3 FROM fragmento));

\echo '--- Cada fila cae en el fragmento de su región ---'
INSERT INTO especie (nombre_comun, nombre_cientifico, humedad_ideal_min, humedad_ideal_max,
                     frecuencia_riego_dias, luz, temp_min, temp_max, fuente)
VALUES ('Especie A9', 'Plantae a9', 40, 60, 7, 'indirecta', 15, 28, 'Dato de prueba A9');

-- Un usuario por región, cada uno en un estado de su región:
-- Chihuahua (8, Norte), Querétaro (22, Centro), Yucatán (31, Sur).
INSERT INTO usuario (region_id, usuario_id, nombre, apellidos, correo, password_hash, estado_id)
VALUES (1, '99999999-0000-0000-0000-000000000001', 'N', 'Norte',  'n9@ejemplo.com', repeat('x', 64),  8),
       (2, '99999999-0000-0000-0000-000000000002', 'C', 'Centro', 'c9@ejemplo.com', repeat('x', 64), 22),
       (3, '99999999-0000-0000-0000-000000000003', 'S', 'Sur',    's9@ejemplo.com', repeat('x', 64), 31);

INSERT INTO planta (region_id, planta_id, usuario_id, especie_id, apodo, tipo_espacio)
SELECT u.region_id, md5('a9-' || u.usuario_id)::uuid, u.usuario_id, e.especie_id, 'Planta A9', 'casa'
FROM usuario u CROSS JOIN especie e
WHERE u.usuario_id::text LIKE '99999999-%' AND e.nombre_cientifico = 'Plantae a9';

INSERT INTO cuidado (region_id, planta_id, tipo)
SELECT region_id, planta_id, 'poda' FROM planta WHERE apodo = 'Planta A9';

SELECT pg_temp.verifica('08 cada usuario quedó en la partición de su región (usuario_r1/_r2/_r3)',
       (SELECT bool_and(tableoid::regclass::text = 'usuario_r' || region_id)
        FROM usuario WHERE usuario_id::text LIKE '99999999-%'));
SELECT pg_temp.verifica('09 cada planta quedó en la partición de su región',
       (SELECT bool_and(tableoid::regclass::text = 'planta_r' || region_id)
        FROM planta WHERE apodo = 'Planta A9'));
SELECT pg_temp.verifica('10 cada cuidado quedó en la partición de su región',
       (SELECT bool_and(c.tableoid::regclass::text = 'cuidado_r' || c.region_id) AND count(*) = 3
        FROM cuidado c JOIN planta p USING (region_id, planta_id) WHERE p.apodo = 'Planta A9'));
SELECT pg_temp.verifica('11 una consulta con region_id = 3 solo entra a usuario_r3 (plan de ejecución)',
       pg_temp.plan('SELECT * FROM app.usuario WHERE region_id = 3') LIKE '%usuario_r3%'
       AND pg_temp.plan('SELECT * FROM app.usuario WHERE region_id = 3') NOT LIKE '%usuario_r1%'
       AND pg_temp.plan('SELECT * FROM app.usuario WHERE region_id = 3') NOT LIKE '%usuario_r2%');

\echo '--- Directorio de correos ---'
INSERT INTO directorio_correo (correo_hmac, region_id, usuario_id, fecha_reserva)
VALUES (repeat('1', 64), 1, '99999999-0000-0000-0000-000000000001', now()),
       (repeat('2', 64), 2, '99999999-0000-0000-0000-000000000002', now()),
       (repeat('3', 64), 3, '99999999-0000-0000-0000-000000000003', now()),
       -- Reservas sin usuario: una vieja y una reciente de la región 2, y una vieja de la región 3.
       (repeat('a', 64), 2, '99999999-0000-0000-0000-0000000000aa', now() - interval '1 hour'),
       (repeat('b', 64), 2, '99999999-0000-0000-0000-0000000000bb', now()),
       (repeat('c', 64), 3, '99999999-0000-0000-0000-0000000000cc', now() - interval '1 hour');

SELECT pg_temp.verifica('12 fecha_reserva se llena sola al reservar',
       (SELECT fecha_reserva IS NOT NULL FROM directorio_correo WHERE correo_hmac = repeat('1', 64)));
SELECT pg_temp.verifica('13 fn_ubicar_usuario devuelve la región y el usuario del correo',
       (SELECT region_id = 3 AND usuario_id = '99999999-0000-0000-0000-000000000003'
        FROM fn_ubicar_usuario(repeat('3', 64))));
SELECT pg_temp.verifica('14 un correo no registrado no devuelve nada',
       NOT EXISTS (SELECT 1 FROM fn_ubicar_usuario(repeat('f', 64))));

-- Simulamos que este nodo es el Centro (región 2).
SET LOCAL app.region_local = '2';
SELECT pg_temp.verifica('15 huérfanas: detecta la reserva vieja sin usuario de su región',
       EXISTS (SELECT 1 FROM vw_reservas_huerfanas WHERE correo_hmac = repeat('a', 64)));
SELECT pg_temp.verifica('16 huérfanas: NO marca la reserva reciente (puede estar en curso)',
       NOT EXISTS (SELECT 1 FROM vw_reservas_huerfanas WHERE correo_hmac = repeat('b', 64)));
SELECT pg_temp.verifica('17 huérfanas: NO revisa reservas de otra región',
       NOT EXISTS (SELECT 1 FROM vw_reservas_huerfanas WHERE correo_hmac = repeat('c', 64)));
SELECT pg_temp.verifica('18 huérfanas: un usuario con su reserva no aparece',
       NOT EXISTS (SELECT 1 FROM vw_reservas_huerfanas WHERE correo_hmac = repeat('2', 64)));

INSERT INTO usuario (region_id, usuario_id, nombre, apellidos, correo, password_hash, estado_id)
VALUES (2, '99999999-0000-0000-0000-0000000000dd', 'Sin', 'Directorio', 'sd9@ejemplo.com', repeat('x', 64), 9);
SELECT pg_temp.verifica('19 detecta un usuario de su región sin fila en el directorio',
       EXISTS (SELECT 1 FROM vw_usuarios_sin_directorio
               WHERE usuario_id = '99999999-0000-0000-0000-0000000000dd'));

\echo '--- Permisos (modelo de A7) ---'
SET LOCAL ROLE plantas_api;
SELECT pg_temp.verifica('20 la API puede ubicar usuarios y leer la topología',
       (SELECT count(*) FROM fn_ubicar_usuario(repeat('1', 64))) = 1
       AND (SELECT count(*) FROM fragmento) = 3);
SELECT pg_temp.sin_permiso('21 la API NO puede cambiar la topología del anillo',
  $q$UPDATE fragmento SET nodo_copia = 'norte' WHERE region_id = 1$q$);
SELECT pg_temp.sin_permiso('22 la API NO puede ver las vistas de huérfanas',
  $q$SELECT * FROM vw_reservas_huerfanas$q$);
RESET ROLE;

ROLLBACK;

\echo 'Pruebas de A9 terminadas: si todas dicen OK, A9 cumple en este nodo.'
