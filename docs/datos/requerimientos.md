# A1 · Análisis de requerimientos de la base de datos

Responsable: Alexa Yalee Sánchez Tejeda · Última revisión: 2026-11-26
IA: asistido (Claude), revisado por la responsable. Ver `docs/bitacora-ia.md`.

Este documento define qué guarda la base, qué consultas hace la app con más frecuencia, cuánto va a crecer y qué datos son personales. Es la entrada de A2 (modelo entidad-relación), A3 (esquema SQL) y A4 (índices).

## 1. Dónde vive cada dato

| Tipo de tabla | Tablas | Dónde está |
|---|---|---|
| Fragmentada por `region_id` | usuario, planta, sensor, cuidado, alerta | Cada nodo guarda solo las filas de su región (1 Norte, 2 Centro, 3 Sur) |
| Global (replicada completa) | region, estado, especie, directorio_correo | Copia completa en los 3 nodos |
| Local | auditoria | Cada nodo tiene la suya; no se replica porque guarda datos personales |
| MongoDB por región | lectura_sensor | Base documental, consistencia eventual (A15) |

La fragmentación usa la opción B de regiones (aproximadamente 36/36/28 % de la población). Se confirma con la medición de A13 y se registra en D-01.

## 2. Entidades y atributos

### 2.1 Fragmentadas por región

| Entidad | Atributos | Notas |
|---|---|---|
| Usuario | region_id, usuario_id (UUID), nombre, apellidos, correo, password_hash (scrypt), rol (usuario/admin), estado_id, activo, fecha_registro, fecha_actualizacion | Es la entidad con más datos personales. El correo se guarda en minúsculas y es único dentro de su región. |
| Planta | region_id, planta_id, usuario_id, especie_id, apodo, tipo_espacio (casa, departamento, oficina, patio), ubicacion_descripcion (por ejemplo «sala»), fecha_adquisicion, estatus (activa, fallecida, regalada), humedad_actual, fecha_ultima_lectura, fecha_registro, fecha_actualizacion | Pertenece a un usuario de su misma región y a una especie. `humedad_actual` y `fecha_ultima_lectura` las actualiza la API cada vez que guarda una lectura en MongoDB (ver 2.4). |
| Cuidado | region_id, cuidado_id, planta_id, tipo (riego, fertilizado, poda, trasplante, otro), fecha_hora, cantidad_ml (solo en riego), notas | Un riego es un cuidado de tipo riego (A5). |
| Sensor | region_id, sensor_id, planta_id, tipo (humedad, ambiente), identificador_dispositivo, es_simulado, activo, fecha_instalacion | Distingue el simulador del ESP32. Un sensor real debe tener identificador (MAC o número de serie). |
| Alerta | region_id, alerta_id, planta_id, tipo (humedad_baja, humedad_alta, riego_pendiente, temperatura), mensaje, fecha_generada, estado (pendiente, atendida), fecha_atendida | La genera el trigger de A6. Cubre alertas y recordatorios en una sola tabla. |

### 2.2 Globales

| Entidad | Atributos | Notas |
|---|---|---|
| Especie (catálogo) | especie_id, nombre_comun, nombre_cientifico, humedad_ideal_min, humedad_ideal_max, frecuencia_riego_dias, luz (sombra, indirecta, directa), temp_min, temp_max, cuidados, fuente, fecha_actualizacion | `fuente` es obligatoria por A20. |
| Región | region_id (1 a 3), nombre | |
| Estado | estado_id (clave INEGI 1 a 32), nombre, region_id, poblacion_aprox | La región se guarda como dato, no fija en código, porque la opción B se confirma con A13. |
| directorio_correo | correo_hmac, region_id, usuario_id | `correo_hmac` = HMAC-SHA256 del correo normalizado, con una llave secreta fuera del repo. Ubica la región de un usuario al iniciar sesión y garantiza que el correo sea único en todo el país. Se usa HMAC y no SHA-256 simple porque un correo es fácil de adivinar con una lista de correos. |

### 2.3 Local

| Entidad | Atributos | Notas |
|---|---|---|
| Auditoría | auditoria_id, tabla, operacion (INSERT, UPDATE, DELETE), registro_id, usuario_db, usuario_app, fecha_hora, datos_anteriores (JSONB), datos_nuevos (JSONB) | Para el trigger de A6. `usuario_app` lo manda la API, porque `usuario_db` casi siempre es la cuenta de servicio. |

### 2.4 MongoDB

| Entidad | Campos | Notas |
|---|---|---|
| LecturaSensor | sensor_id, planta_id, region_id, tipo, timestamp y, según el tipo, humedad_suelo_pct o temperatura_c + humedad_relativa_pct | Cada tipo corresponde a LecturaHumedad o LecturaAmbiente del dominio de Python. El timestamp sirve para la expiración de A15. |

**Problema de diseño y solución.** Un trigger de PostgreSQL no puede reaccionar a una lectura que se inserta en MongoDB, y una consulta SQL no puede hacer JOIN con MongoDB. Por eso la API, al guardar cada lectura, también actualiza `planta.humedad_actual` y `planta.fecha_ultima_lectura`. El trigger de alertas (A6) se dispara con ese UPDATE, y Q10 se resuelve dentro de PostgreSQL.

## 3. Consultas más frecuentes

Todas las consultas a tablas fragmentadas filtran por `region_id`, para que PostgreSQL entre solo a la partición de esa región. Cada consulta frecuente tiene su índice en A4.

| ID | Consulta (lo que hace la app) | Tablas | Filtro y orden | Frecuencia | Índice (A4) |
|---|---|---|---|---|---|
| Q1 | Iniciar sesión: ubicar al usuario por correo | directorio_correo, usuario | correo_hmac → region_id, usuario_id | Muy alta | Llave primaria del directorio y de usuario |
| Q2 | Listar las plantas de un usuario | planta | region_id, usuario_id | Muy alta | idx_planta_usuario |
| Q3 | Ver el detalle de una planta con su especie | planta, especie | region_id, planta_id; JOIN por especie_id | Alta | Llaves primarias |
| Q4 | Historial de cuidados de una planta, del más reciente al más antiguo | cuidado | region_id, planta_id; orden fecha_hora DESC | Alta | idx_cuidado_planta_fecha |
| Q5 | Último riego de cada planta de un usuario y cuándo toca el siguiente | cuidado, planta, especie | region_id, usuario_id, tipo = 'riego', último fecha_hora + frecuencia_riego_dias | Alta | idx_cuidado_riego (parcial) |
| Q6 | Alertas pendientes de un usuario | alerta, planta | region_id, usuario_id vía planta, estado = 'pendiente', orden fecha_generada DESC | Alta | idx_alerta_pendiente (parcial) |
| Q7 | Buscar especies por nombre en el catálogo | especie | nombre_comun ILIKE '%texto%' | Media | idx_especie_nombre_trgm (trigramas) |
| Q8 | Últimas lecturas de un sensor | lectura_sensor (MongoDB) | sensor_id, orden timestamp DESC, límite N | Muy alta | En A15 |
| Q9 | Lecturas de una planta en un rango de fechas, para gráficas con pandas | lectura_sensor (MongoDB) | planta_id, rango de timestamp | Media | En A15 |
| Q10 | Plantas activas con lectura reciente cuya humedad está fuera del rango ideal de su especie | planta, especie | region_id, estatus = 'activa', fecha_ultima_lectura reciente, humedad_actual fuera de [min, max] | Media | idx_planta_lectura_activa (parcial) |

Consultas de reporte, de baja frecuencia (gráficas de Python). No llevan índice propio porque agregan la tabla completa:

| ID | Consulta | Tablas | Nota |
|---|---|---|---|
| Q11 | Plantas con más alertas de riego | alerta, planta | Agrupa por planta dentro de cada región |
| Q12 | Especies por región | planta, especie | Consulta **distribuida**: necesita los 3 nodos |

## 4. Escrituras más frecuentes

| ID | Escritura | Dónde | Frecuencia |
|---|---|---|---|
| W1 | Guardar una lectura de sensor | MongoDB | Muy alta (una por sensor cada 15 minutos) |
| W2 | Actualizar humedad_actual y fecha_ultima_lectura de la planta | planta | Muy alta (una por cada lectura de humedad) |
| W3 | Registrar un cuidado (riego, poda…) | cuidado | Alta |
| W4 | Generar y atender alertas | alerta | Media |
| W5 | Registrar usuario o planta | usuario, directorio_correo, planta | Baja |

## 5. Volumen esperado

Las cifras son **supuestos de diseño**. Sirven para elegir tecnologías y no son mediciones. Se comparan con los datos reales en A16 y A18.

| Supuesto | Valor |
|---|---|
| Usuarios (escenario de diseño) | 100 000 |
| Plantas por usuario | 3 |
| Plantas con sensor | 50 % |
| Intervalo entre lecturas | 15 minutos (96 al día por sensor) |
| Cuidados por planta | 1 por semana (≈ 52 al año) |
| Alertas por planta | 1 por semana (≈ 52 al año) |

| Tabla | Filas estimadas | Crecimiento |
|---|---|---|
| usuario | 100 000 | Lento |
| planta | 300 000 | Lento |
| sensor | 150 000 | Lento |
| cuidado | ≈ 15.6 millones al año | Constante |
| alerta | ≈ 15.6 millones al año | Constante |
| lectura_sensor (MongoDB) | 150 000 × 96 = 14.4 millones al día (≈ 5 260 millones al año) | Muy rápido |
| especie | 30 a cientos | Casi fijo |
| estado / región | 32 / 3 | Fijo |

Conclusiones del volumen:
- Las lecturas de sensores crecen miles de veces más rápido que todo lo demás. Por eso van en MongoDB, con expiración automática (A15), y no en PostgreSQL.
- cuidado y alerta son las tablas de PostgreSQL que más crecen. Por eso sus índices de A4 son parciales o están ordenados por fecha.
- El laboratorio carga 100 000 registros sintéticos (A13), repartidos por región en proporción a la población. Con esa carga se repiten los `EXPLAIN` en A18.

## 6. Datos personales

| Dato | Tabla | Categoría | Protección |
|---|---|---|---|
| nombre, apellidos | usuario | Identificativo | Fragmentado por región; enmascarado en vistas (A7) |
| correo | usuario | Contacto e identificativo | Único por región; en el directorio solo va como HMAC |
| password_hash | usuario | Credencial | scrypt con sal; nunca se guarda la contraseña |
| estado_id | usuario | Ubicación aproximada | Solo a nivel estado, no se guarda domicilio |
| tipo_espacio, ubicacion_descripcion | planta | Hábitos y entorno (casa, oficina, «recámara») | Texto corto, sin dirección |
| fecha_hora de cuidados y lecturas | cuidado, lectura_sensor | Hábitos: muestran cuándo está la persona en casa | Fragmentado; las lecturas expiran (A15) |
| notas | cuidado | Texto libre: puede traer cualquier dato | Límite de 500 caracteres; la app debe advertir que no se escriban datos personales |
| datos_anteriores, datos_nuevos | auditoria | Copia de cualquiera de los anteriores | Tabla local, no se replica; acceso solo administrativo (A7) |

Medidas comunes: conexiones con TLS y cifrado en reposo (A14), respaldo cifrado (A17) y cuentas separadas para administrar y para el servicio (A7).

> **Pendiente de revisión con Andrea (Seguridad):** la clasificación legal de cada dato según la LFPDPPP (DOF 2025-03-20), el aviso de privacidad y qué pasa al ejercer el derecho de cancelación. Hoy el esquema borra en cascada todo lo del usuario. Esta sección no la redacta la IA.
