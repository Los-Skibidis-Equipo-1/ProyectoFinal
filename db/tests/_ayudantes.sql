-- =====================================================================
-- Funciones de apoyo para las pruebas (se cargan con \ir en cada sesión;
-- viven en pg_temp y desaparecen al desconectarse).
-- IA: generado y revisado (Claude) — ver docs/bitacora-ia.md
-- =====================================================================

-- Comprueba que una condición sea verdadera ya.
CREATE OR REPLACE FUNCTION pg_temp.verifica(prueba text, condicion boolean)
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    IF condicion IS TRUE THEN
        RAISE NOTICE 'OK    %', prueba;
    ELSE
        RAISE EXCEPTION 'FALLO %', prueba;
    END IF;
END;
$$;

-- Espera hasta `segundos` a que una consulta booleana dé true (para la
-- replicación asíncrona). Informa cuánto tardó.
CREATE OR REPLACE FUNCTION pg_temp.espera(prueba text, consulta text, segundos numeric DEFAULT 15)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE
    inicio timestamptz := clock_timestamp();
    listo  boolean;
BEGIN
    LOOP
        EXECUTE consulta INTO listo;
        IF listo IS TRUE THEN
            RAISE NOTICE 'OK    %  (% s)', prueba,
                round(extract(epoch FROM clock_timestamp() - inicio)::numeric, 2);
            RETURN;
        END IF;
        IF clock_timestamp() - inicio > make_interval(secs => segundos) THEN
            RAISE EXCEPTION 'FALLO %  -> no pasó en % s', prueba, segundos;
        END IF;
        PERFORM pg_sleep(0.2);
    END LOOP;
END;
$$;

-- Ejecuta una sentencia que DEBE fallar con un SQLSTATE dado.
CREATE OR REPLACE FUNCTION pg_temp.debe_fallar(prueba text, sentencia text, sqlstate_esperado text)
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    BEGIN
        EXECUTE sentencia;
    EXCEPTION WHEN OTHERS THEN
        IF SQLSTATE = sqlstate_esperado THEN
            RAISE NOTICE 'OK    %  (%)', prueba, SQLERRM;
            RETURN;
        END IF;
        RAISE EXCEPTION 'FALLO %  -> falló con % (%), se esperaba %',
            prueba, SQLSTATE, SQLERRM, sqlstate_esperado;
    END;
    RAISE EXCEPTION 'FALLO %  -> no falló y debía fallar', prueba;
END;
$$;

GRANT EXECUTE ON FUNCTION pg_temp.verifica(text, boolean),
                          pg_temp.espera(text, text, numeric),
                          pg_temp.debe_fallar(text, text, text) TO PUBLIC;
