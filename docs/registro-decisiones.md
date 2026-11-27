# Registro de decisiones

Aquí anotamos las decisiones grandes del proyecto, con el motivo y los datos que usamos. Si una decisión cambia, no se borra: se agrega una nueva y la vieja queda marcada como reemplazada.

---

## D-01: Cómo se reparte y se replica la base de datos

- **Fecha:** 2026-11-27
- **Tarea:** A8 (Closes #8)
- **Hecha por:** Alexa y Andrea
- **Revisa:** Chris
- **Estado:** aceptada. Quedan mediciones y pruebas pendientes (sección 12); solo pueden cambiar cuál nodo escribe las tablas globales o, con A13, A16 y A18, el diseño de regiones.

### 1. Contexto

El sistema es de alcance nacional y guarda datos personales (nombre, correo, plantas y hábitos de cada persona). Con una sola base central pasarían tres cosas:

- Si cae ese servidor, cae todo el país.
- Todos los usuarios pagan la distancia al mismo servidor.
- Los datos personales de todo el país quedan juntos en un solo lugar.

Fragmentar por región resuelve esto: los datos de cada usuario viven cerca de él, una caída solo afecta a una región y cada nodo solo guarda los datos personales de su zona. Además es lo que piden los lineamientos (fragmentación y replicación entre nodos).

Tenemos tres equipos, así que son tres nodos y tres regiones: Norte, Centro y Sur.

### 2. Llave de fragmentación

Decidimos fragmentar con `PARTITION BY LIST (region_id)`, usando la **opción B** de regiones (reajustadas). Mueve Jalisco, Colima, Nayarit, Aguascalientes y San Luis Potosí a Norte y Puebla a Sur; Veracruz se queda en Sur.

Con el Censo 2020 (cifras en `db/02_datos_base.sql`) queda así:

| Región | Estados | Población | % |
|---|---|---|---|
| Norte | 15 | 44,757,715 | 35.5 |
| Centro | 8 | 45,883,947 | 36.4 |
| Sur | 9 | 35,372,362 | 28.1 |

La suma da 126,014,024, que es el total nacional del Censo 2020. Las cifras por estado todavía hay que revisarlas una por una contra INEGI (sección 12).

**Alternativas que descartamos**

- **Opción A, regiones geográficas sin reajustar** (la B sin mover los 6 estados). Con las cifras del archivo queda en 24.0 % Norte, 53.2 % Centro y 22.8 % Sur. Es la más fácil de explicar, pero Centro cargaría con más de la mitad del país y su nodo sería el cuello de botella.
- **Fragmentar por hash de `usuario_id`.** Reparte perfecto, pero se pierde la localidad: las consultas por región (Q10 y Q12 de A1) tendrían que preguntarle a los tres nodos, ya no se puede explicar con un mapa y no ayuda con la protección de datos por zona. Además obligaba a rehacer A3 a A7 y las 97 pruebas, porque todas las llaves y particiones están pensadas para `region_id`.

**Por qué B**

- **Flexibilidad.** La región de cada estado es un dato (columna `estado.region_id`), no algo fijo en el código. Si más adelante hay que mover un estado, se cambia esa columna y se reubican las filas de ese estado, sin rediseñar el esquema.
- **Localidad de los datos.** El usuario, sus plantas, sensores, cuidados y alertas quedan juntos en el mismo nodo, y las llaves foráneas compuestas `(region_id, ...)` lo obligan.
- **Consultas por región.** Q10 y Q12, que filtran por región, tocan una sola partición. Con hash tocarían las tres.
- **Se explica con geografía.** "Estos estados van a este nodo" se entiende sin ser experto en bases de datos.

### 3. Cómo se replican los fragmentos

Decidimos usar **replicación lógica de las particiones, con failover manual** (con script), en anillo: Norte → Centro → Sur → Norte. Cada nodo tiene su partición para leer y escribir, y además una copia de solo lectura de la partición del nodo anterior.

Si se cae un nodo, su copia está en el siguiente del anillo, y ahí se promueve a mano.

**Cómo es la promoción.** Un script (`promover.sh`) comprueba que al menos 2 de los 3 nodos ven caído al nodo en cuestión y solo entonces habilita la escritura en la copia y cambia en la API cuál es el nodo activo de esa región.

**Cuando el nodo caído regresa.** Arranca en solo lectura, se vacía su partición y se vuelve a suscribir con `copy_data` para ponerse al día. Vaciar la partición descarta lo que no alcanzó a replicarse antes de la caída: es la misma pérdida que declaramos en la sección 8, solo que aquí tiene nombre. Cuando termina de ponerse al día **se queda como copia**; volver a ser el primario de su región es un cambio planeado (el mismo script, en un horario que acordemos), no algo automático, para no provocar otro corte sin necesidad. Ese procedimiento es el que se muestra en A12.

**Alternativa que descartamos: una instancia por región con réplica física y Patroni.** Tiene elección automática de primario, pero cada equipo correría dos instancias de PostgreSQL, un miembro de etcd, MongoDB y el contenedor de seguridad sobre Docker Desktop y WSL2. etcd necesita latencia estable, y con equipos en casa, Wi-Fi y una VPN en estrella pasando por Azure, un timeout mal calibrado provoca elecciones falsas justo cuando más estorban. Además A19 pide dos ensayos seguidos sin tropiezos, y menos piezas ayudan. Si hubiera infraestructura estable, Patroni seguiría siendo la mejor opción.

### 4. Quién escribe las tablas globales

Las tablas globales son `region`, `estado`, `especie` y `directorio_correo`. Un solo nodo las escribe y los otros dos se suscriben. Casi no cambian (menos el directorio), así que no justifica tener varios escritores y arriesgar conflictos.

El nodo escritor se elige con estos criterios, en este orden:

1. **Disponibilidad:** más horas encendido al día, y por cable antes que por Wi-Fi.
2. **Latencia a Azure por la VPN:** menor promedio y menor variación.
3. **Desempate:** el nodo cuyo responsable puede intervenir más rápido si algo falla.

| Nodo | Horas encendido | Cable / Wi-Fi | Ping promedio | Ping máx. | Pérdida |
|---|---|---|---|---|---|
| Norte | pendiente | pendiente | pendiente (C9) | pendiente | pendiente |
| Centro | pendiente | pendiente | pendiente (C9) | pendiente | pendiente |
| Sur | pendiente | pendiente | pendiente (C9) | pendiente | pendiente |

**Escritor elegido:** pendiente de llenar la tabla. La latencia depende de que Chris termine la VPN (C9).

### 5. Replicación síncrona solo para el directorio

Todo se replica de forma asíncrona, menos `directorio_correo`. Ahí configuramos `synchronous_standby_names = 'ANY 1 (...)'` con los dos suscriptores y dejamos `synchronous_commit = local` por defecto. Las transacciones que escriben el directorio hacen `SET LOCAL synchronous_commit = on`, y así esperan a que al menos un suscriptor confirme.

Lo hicimos así por esto: la llave primaria del escritor ya impide que un correo se registre dos veces. Lo que evita la replicación síncrona es **perder una reserva ya confirmada si el escritor se cae**. Si se pierde, después del cambio de escritor el mismo correo se podría registrar otra vez en otra región, y eso rompe el login. Pagar la espera ahí sale barato porque solo se escribe al registrarse o borrar cuenta.

**Si se caen los dos suscriptores:** las escrituras al directorio se quedan esperando. La API pone un timeout y responde 503 en registro y baja de cuenta. El login y todo lo demás siguen funcionando porque solo leen. No bajamos la sincronía automáticamente: preferimos no dejar registrar usuarios un rato a arriesgar un directorio inconsistente. Si el timeout corta una espera, la fila puede haberse guardado localmente sin confirmación; esa fila la limpia la revisión de huérfanas (sección 6).

### 6. Directorio de correos

**Alta de usuario**

1. La API genera el `usuario_id` (UUID).
2. Reserva el correo en el directorio (`correo_hmac`, `region_id`, `usuario_id`), con escritura síncrona.
3. Crea el usuario en el nodo de su región.
4. Si el paso 3 falla, borra la reserva del paso 2.

**Baja de usuario:** el orden es el inverso. Primero se borra el usuario en su región y al final su fila del directorio. Así, si algo falla a la mitad, lo que sobra es una reserva sin usuario y no un usuario que no se puede encontrar.

**Login desde otro nodo:** el directorio llega a los otros nodos de forma asíncrona, así que un usuario recién registrado puede tardar unos segundos en poder iniciar sesión desde un nodo distinto al del registro. Lo aceptamos.

**Filas huérfanas.** Para poder saber qué tan vieja es una reserva, se agregará a `directorio_correo` la columna `fecha_reserva timestamptz NOT NULL DEFAULT now()`. Es un cambio a A3 y se hace en A9 o A11. Una tarea periódica en cada nodo **detecta** dos casos:

- Fila del directorio con la región de ese nodo y sin usuario correspondiente en su partición. Si su `fecha_reserva` tiene más de unos minutos, es una reserva que quedó a medias.
- Usuario sin fila en el directorio. No debería pasar con este orden, así que no se arregla solo: se reporta para revisarlo a mano.

Cada nodo es suscriptor del directorio, así que **no borra en su copia** (se desincronizaría). Las reservas huérfanas se borran en el nodo que escribe las globales, y de ahí se replican.

### 7. MongoDB

Decidimos usar **un MongoDB independiente por región**, sin réplica entre ellos y **sin llave de sharding**. No hace falta repartir una colección entre nodos porque cada región ya tiene su propia instancia. Aun así el volumen no es chico: A1 estima 14.4 millones de lecturas al día en el escenario de diseño, así que el TTL importa para el almacenamiento.

Las lecturas se consultan por sensor y por planta en un rango de fechas, así que los índices son:

- `{ sensor_id: 1, timestamp: -1 }` para pedir las últimas lecturas de un sensor.
- `{ planta_id: 1, timestamp: 1 }` para las gráficas por planta y rango de fechas (Q9).
- Índice TTL sobre `timestamp` para que las lecturas viejas se borren solas (el plazo exacto se fija en A15).

Usamos `timestamp`, igual que en `requerimientos.md`.

**Si se cae el nodo:** la API reintenta unas pocas veces (por ejemplo 3 intentos en unos 30 segundos). Si sigue caído, esa lectura se pierde. No hacemos una cola persistente: son lecturas de sensores caseros con expiración, y una lectura faltante se compensa con la siguiente. Como la API actualiza `planta.humedad_actual` solo después de guardar en MongoDB, una lectura perdida tampoco deja datos a medias en PostgreSQL.

### 8. Tabla CAP

| Pieza | Postura | Qué pasa en una partición o caída |
|---|---|---|
| Fragmentos de PostgreSQL | CP | Cada región tiene un solo nodo que escribe. Si ese nodo queda aislado, se prefiere no aceptar escrituras de esa región antes que escribir en dos lados. |
| `directorio_correo` | CP | Escritura síncrona con `ANY 1`. Si no hay a quién confirmarle, no se escribe. |
| Tablas globales (resto) | CP al escribir, lectura local | Un solo escritor. Cada nodo puede seguir leyendo su copia, aunque tenga un pequeño retraso. |
| MongoDB (lecturas de sensores) | AP, consistencia eventual | Cada nodo acepta las lecturas de los sensores sin coordinarse con nadie. No hay réplica, así que si el nodo cae, lo que no se guardó se pierde (sección 7). |

**Qué evita que haya dos primarios de una misma región.** Con failover manual no hay quórum automático, y no lo vamos a presentar como si lo hubiera. Lo que lo evita es el procedimiento:

- La API solo escribe en el nodo que tiene marcado como activo para esa región, y esa marca vive en un solo lugar (la API, en Azure). Si Azure está caído, nadie escribe, y por lo tanto no se crean dos primarios.
- `promover.sh` exige que al menos 2 de 3 nodos vean caído al nodo antes de promover. Eso imita el quórum de 2 de 3, pero lo aplica un script, no el motor.
- El nodo que regresa arranca con `default_transaction_read_only = on` y no vuelve a escribir hasta ser resincronizado. Ojo: esto es una protección contra errores, no una barrera, porque cualquier sesión puede hacer `SET default_transaction_read_only = off` o `SET TRANSACTION READ WRITE`. Lo que de verdad evita escrituras es la marca única en la API, junto con RLS (sección 9).

**Concesión: la API en Azure es un punto único de falla para las escrituras.** Es el mismo argumento de arriba visto desde el otro lado: como todo pasa por una sola API, no hay dos primarios, pero si Azure se cae (o se acaba el crédito), no se escribe en ninguna región. Los nodos siguen vivos, pero sin API nadie les escribe.

**Pérdida posible de escrituras.** Como la replicación es asíncrona, lo que el nodo primario alcanzó a confirmar pero no a mandar al suscriptor se pierde si el primario cae para siempre (RPO mayor que cero). Esto no pasa en el directorio, que es síncrono. Durante las pruebas de A12 vamos a medir el retraso de replicación para poner un número aquí.

### 9. Protección de la copia del anillo

Las particiones que son copia de otro nodo no deben recibir escrituras de la API, porque se desincronizarían. Esto **todavía no está implementado**; se agregará en A11, con dos capas:

1. **Permisos sobre las particiones copia:** a `plantas_app` se le quitarán INSERT, UPDATE y DELETE (en `db/06_roles.sql`), y se le dejará solo SELECT. Esto bloquea el acceso directo a la partición.
2. **Row Level Security en la tabla padre.** En PostgreSQL, un INSERT que entra por la tabla padre se revisa con los permisos del padre, no de la partición, así que el REVOKE solo no basta. Se agregarán dos políticas en cada tabla fragmentada:
   - **SELECT:** deja a `plantas_app` leer todas las filas, incluidas las copias. Hace falta porque al activar RLS todo lo que no tenga política queda bloqueado, incluso las lecturas, y sin esta la API dejaría de ver datos.
   - **INSERT, UPDATE y DELETE:** solo deja escribir filas cuyo `region_id` esté en la lista de regiones locales.

   La región local se guarda con `ALTER DATABASE plantas SET app.region_local = '1'` (el valor que corresponda a cada nodo). Después de una promoción el nodo atiende dos regiones, la suya y la del nodo caído, así que el valor es una **lista**, por ejemplo `'2,1'`, y la política la compara así: `region_id = ANY (string_to_array(current_setting('app.region_local'), ',')::smallint[])`.

La suscripción no se ve afectada, porque aplica los cambios como dueña de las tablas y no pasa por la política (no se usa `FORCE ROW LEVEL SECURITY`). Las vistas de A7 tampoco, porque consultan como dueñas, y los triggers de auditoría tampoco, porque son `SECURITY DEFINER`. `promover.sh` agrega la región del nodo caído a la lista al promover y la quita cuando el nodo regresa; como el `ALTER DATABASE` solo aplica a conexiones nuevas, el script también tiene que hacer que la API reconecte.

En A11 se probará que un INSERT por la tabla padre con el `region_id` de otra región falle.

### 10. Plan si se cae el nodo que escribe las globales

Un suscriptor pasa a ser escritor, a mano:

1. Confirmar que el escritor de verdad está caído (mismo criterio de 2 de 3 que en `promover.sh`).
2. En el suscriptor elegido, crear la publicación de las tablas globales.
3. En el otro suscriptor, apuntar la suscripción al nuevo escritor sin volver a copiar los datos. **Ojo:** el nuevo escritor tiene su propio slot de replicación, así que esto puede saltarse o repetir cambios. Se prueba en A12 y, si falla, se vuelve a suscribir con `copy_data`.
4. Cambiar en la API el nodo que escribe las globales y reconfigurar el `ANY 1` del directorio.
5. Cuando el viejo escritor regrese, se vuelve suscriptor y se pone al día; no vuelve a ser escritor sin una decisión del equipo.

Mientras tanto, la app sigue leyendo catálogo y directorio en cada nodo; solo se detienen los registros nuevos.

### 11. Criterios de revisión

Usamos dos criterios, porque responden preguntas distintas.

**(a) Validar el generador (A13).** A13 asigna los 100,000 registros a los estados en proporción a su población. Si el porcentaje real de algún fragmento se desvía **más de 1 punto porcentual** del porcentaje de población de su región, el generador tiene un error. La razón: con 100,000 filas, el ruido normal del muestreo es de unos 0.15 puntos (raíz de p(1−p)/n con p cerca de 0.36). Un punto son más de 6 veces ese ruido, así que una desviación mayor no es casualidad. Este criterio no dice nada del diseño de las regiones, porque los datos ya salen proporcionales a la población por construcción.

**(b) Revisar las regiones.** Si la parte de carga de un nodo pasa de **40 %** del total, se revisa el diseño de las regiones. Con la opción B, la región más grande tiene 36.4 % de la población, así que hay margen de unos 3.6 puntos antes de llegar al umbral. La carga se mide de tres formas: filas por fragmento, crecimiento de almacenamiento (A16) y tiempos de consultas (A18).

### 12. Pendientes

- **Población:** verificar contra INEGI las cifras por estado de `db/02_datos_base.sql` (el total ya coincide).
- **Opción A:** confirmar con una consulta los porcentajes de la sección 2.
- **Latencia a Azure:** ping por la VPN desde cada computadora. Depende de C9 (Chris).
- **Disponibilidad:** horas encendida por día y cable o Wi-Fi en cada computadora.
- **Escritor de las globales:** elegir con la tabla de la sección 4 cuando estén esas mediciones.
- **`fecha_reserva` en el directorio:** cambio a A3, se hace en A9 o A11.
- **RLS y permisos de la copia del anillo:** se implementan y prueban en A11.
- **Retraso de replicación y cambio de suscripción:** se miden y prueban en A12.
- **Borrado de datos personales (B20):** Andrea y Alexa deben decidir si al cancelar cuenta se borra o se anonimiza, y qué queda en la auditoría local. Hoy el esquema borra en cascada.
- **Confirmación final:** la medición de A13 y la carga de A16 y A18 confirman o corrigen la opción B.
