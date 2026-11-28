# A12 · Guion de la prueba de pérdida de nodo y de partición de red

Responsable: Alexa Yalee Sánchez Tejeda · Decisión de diseño: `docs/registro-decisiones.md` (D-01 §3 y §8)
IA: asistido (Claude), revisado por la responsable. Ver `docs/bitacora-ia.md`.

La demostración prueba tres cosas: (1) si se cae el nodo de una región, su copia la atiende sin perder lo ya replicado; (2) nunca hay dos nodos escribiendo la misma región; (3) cuando el nodo regresa, se sincroniza solo. El failover es **manual con script** (`db/failover/promover.sh`), como se decidió en D-01, y exige que 2 de 3 nodos vean caído al nodo.

## Topología del ensayo

| Nodo | Primario de | Copia de | Papel en el ensayo |
|---|---|---|---|
| Norte | región 1 | región 3 | Tercer nodo (da el segundo voto del quórum); escritor de las globales |
| Centro | región 2 | región 1 | **Víctima** |
| Sur | región 3 | región 2 | Copia de la víctima: aquí se promueve la región 2 |

Se usa Centro como víctima porque no es el escritor de las globales (si cae el escritor se sigue D-01 §10).

## Ensayo automático (para practicar y para la evidencia)

```powershell
powershell -ExecutionPolicy Bypass -File db\lab\ensayo_a12.ps1
```

Corre los dos escenarios desde cero y deja `docs/evidencias/a12_ensayo.txt` (cada paso con hora y resultado) y `a12_logs_<nodo>.txt` (logs de PostgreSQL). Debe terminar con «ENSAYO DE A12 COMPLETO». A19 pide hacerlo **dos veces seguidas sin tropiezos**.

## Demostración en vivo, paso a paso

Antes de empezar: laboratorio recién instalado (`iniciar_lab.ps1`) y una terminal en la raíz del repo. Para no escribir tanto, primero se cargan dos ayudas:

```powershell
Get-Content .env | ForEach-Object { if ($_ -match '^\s*([^#=\s]+)\s*=\s*(.*)$') { Set-Item -Path "env:$($matches[1])" -Value $matches[2] } }
$fo = @('-e','NODO_NORTE_HOST=pg-norte','-e','NODO_CENTRO_HOST=pg-centro','-e','NODO_SUR_HOST=pg-sur','-e',"PGPASSWORD=$env:POSTGRES_PASSWORD",'-e',"PG_PASS_REPLICA=$env:PG_PASS_REPLICA",'-e','ESCRITOR_GLOBALES=norte')
function api($nodo, $sql) { docker exec "pg-$nodo" psql -U postgres -d plantas -c 'SET ROLE plantas_api' -c 'SET search_path TO app' -c $sql }
function ver($nodo, $sql) { docker exec "pg-$nodo" psql -U postgres -d plantas -c $sql }
```

### Escenario 1 · Pérdida de nodo

| # | Qué se hace | Comando | Qué se ve / qué decir | Captura |
|---|---|---|---|---|
| 1 | Estado normal | `ver centro "SHOW app.region_local"` y `ver sur "SHOW app.region_local"` | Centro atiende la región 2, Sur la 3. | ✔ |
| 2 | La API escribe en Centro | `api centro "INSERT INTO usuario (region_id,nombre,apellidos,correo,password_hash,estado_id) VALUES (2,'Ana','Demo','ana@ejemplo.com',repeat('x',64),22)"` | Funciona. | |
| 3 | Llega a su copia | `ver sur "SELECT nombre FROM app.usuario_r2"` | Ana aparece en Sur: replicación del anillo. | ✔ |
| 4 | Sur no puede escribir la región 2 | `api sur "INSERT INTO usuario (region_id,nombre,apellidos,correo,password_hash,estado_id) VALUES (2,'X','Y','x@ejemplo.com',repeat('x',64),22)"` | `violates row-level security`: la copia es de solo lectura para la API. | ✔ |
| 5 | **Se cae Centro** | `docker stop pg-centro` | | |
| 6 | Failover | `docker exec @fo pg-sur bash /tmp/db/failover/promover.sh centro` | 3 rondas de quórum (≈10 s) y «la región 2 ahora la atiende 'sur'». Explicar por qué se esperan 3 rondas y por qué hace falta el voto de Norte. | ✔ |
| 7 | Sur ya escribe la región 2 | el mismo INSERT del paso 4 con otro correo | Ahora sí funciona. | ✔ |
| 8 | **Regresa Centro** | `docker start pg-centro` | | |
| 9 | Reincorporación | `docker exec @fo pg-sur bash /tmp/db/failover/reincorporar.sh centro` | Descarta su copia local, se suscribe a Sur y compara conteos: «Sincronizado». | ✔ |
| 10 | Centro tiene lo escrito durante la caída | `ver centro "SELECT nombre FROM app.usuario_r2"` | Aparecen Ana y el usuario del paso 7. Centro queda como copia; volver a ser primario es un cambio planeado. | ✔ |

### Escenario 2 · Partición de red

Reinstalar el laboratorio (`iniciar_lab.ps1`) y cargar las ayudas otra vez.

| # | Qué se hace | Comando | Qué se ve / qué decir | Captura |
|---|---|---|---|---|
| 1 | Aislar Centro (sigue encendido) | `docker network disconnect plantas-lab pg-centro` | | |
| 2 | Intento inmediato de promover | `docker exec @fo pg-sur bash /tmp/db/failover/promover.sh centro` | Si Norte todavía ve conectado a Centro, **se niega**: así se evita promover por un corte momentáneo. Esperar ~15 s y repetir. | ✔ |
| 3 | Alguien le escribe a Centro aislado | `ver centro "INSERT INTO app.usuario (region_id,nombre,apellidos,correo,password_hash,estado_id) VALUES (2,'Aislado','Demo','aislado@ejemplo.com',repeat('x',64),22)"` | Centro lo acepta localmente, pero nadie más lo ve: la API real ya no le escribe porque la marca de la región vive en un solo lugar. | ✔ |
| 4 | Promover (cuando Norte ya no lo vea) | el comando del paso 2 | «Quórum: 2 de 3 nodos ven caído a 'centro'». | ✔ |
| 5 | Sur escribe la región 2 | `api sur "INSERT ... (2,'Durante','Particion','dp@ejemplo.com',...)"` | Funciona. | |
| 6 | Se repara la red | `docker network connect plantas-lab pg-centro` | | |
| 7 | Reincorporación | `docker exec @fo pg-sur bash /tmp/db/failover/reincorporar.sh centro` | Informa cuántas filas descarta (incluye la escrita aislada). | ✔ |
| 8 | Resultado | `ver centro "SELECT nombre FROM app.usuario_r2"` y `ver sur "SELECT nombre FROM app.usuario_r2"` | «Aislado» no está en ningún lado; «Durante» está en los dos. Es la pérdida declarada en D-01 §8 (RPO > 0) y la prueba de que no hubo dos primarios. | ✔ |

## Qué responder si preguntan

- **¿Por qué manual y no automático?** D-01 §3: con equipos en casa, Wi-Fi y VPN por Azure, una elección automática mal calibrada promueve por cortes falsos. Patroni sería la opción con infraestructura estable.
- **¿Qué evita dos primarios?** La API escribe solo en el nodo marcado como activo; `promover.sh` exige 2 de 3 votos; y RLS hace que la API solo escriba las regiones de `app.region_local`. El paso 2 del escenario 2 muestra que el script se niega si el tercer nodo todavía ve al caído.
- **¿Qué se pierde?** Lo que el nodo caído confirmó y no alcanzó a replicar (asíncrono). El directorio de correos no, porque es síncrono (`ANY 1`).
- **¿Qué cambia con las 3 computadoras?** Solo las direcciones (`NODO_*_HOST` = IP de la VPN) y que «apagar» y «aislar» se hacen en la computadora real. Los scripts son los mismos.

## Pendiente para hacerlo en las 3 computadoras (después de C9)

- Medir el tiempo real de cada paso y el retraso de replicación (D-01 §8 pide el número).
- Repetirlo con la red de verdad: desconectar el Wi-Fi o la VPN de un equipo en lugar de `docker network disconnect`.
- Regreso planeado del primario original (cambio de vuelta de la región 2 a Centro).
