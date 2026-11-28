# =====================================================================
# A12 · Ensayo de pérdida de nodo y de partición de red (laboratorio)
#
# Corre los dos escenarios de D-01 con los 3 contenedores y deja la
# evidencia (guion ejecutado, salida de los scripts y logs de PostgreSQL):
#   Escenario 1  PÉRDIDA DE NODO      docker stop  del nodo víctima
#   Escenario 2  PARTICIÓN DE RED     docker network disconnect (sigue vivo)
# En ambos: promover.sh en su copia, escribir en la región promovida,
# y al volver, reincorporar.sh (regresa como copia).
#
# Uso (raíz del repo, Docker Desktop abierto; tarda unos 6 minutos):
#   powershell -ExecutionPolicy Bypass -File db\lab\ensayo_a12.ps1
# Evidencias: docs\evidencias\a12_ensayo.txt y a12_logs_<nodo>.txt
# Responsable: Alexa Yalee Sánchez Tejeda · IA: generado y revisado (Claude)
# =====================================================================

$ErrorActionPreference = 'Continue'
# Que la salida de docker/psql (UTF-8) se lea bien en la consola y en las evidencias.
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$raiz = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$envFile = Join-Path $raiz '.env'
$log = Join-Path $raiz 'docs\evidencias\a12_ensayo.txt'
Set-Content -Path $log -Value "A12 · Ensayo de pérdida de nodo y partición de red — $(Get-Date -Format 'yyyy-MM-dd HH:mm')" -Encoding UTF8

function Log([string]$texto, [string]$color = 'White') {
    $linea = '[{0}] {1}' -f (Get-Date -Format 'HH:mm:ss'), $texto
    Write-Host $linea -ForegroundColor $color
    Add-Content -Path $log -Value $linea -Encoding UTF8
}
function Fallar([string]$mensaje) { Log "ERROR: $mensaje" 'Red'; exit 1 }

# Corre docker con los argumentos dados, registra la salida y regresa el código de salida.
function Docker-Log([string[]]$argumentos) {
    $salida = & docker @argumentos 2>&1 | ForEach-Object { "$_" }
    $codigo = $LASTEXITCODE
    foreach ($l in $salida) { if ($l.Trim()) { Log "    $l" 'Gray' } }
    return $codigo
}
# Consulta de una sola respuesta como postgres en un nodo.
function Valor([string]$c, [string]$sql) {
    return ((& docker exec $c psql -U postgres -d plantas -X -q -tA -c $sql 2>$null) -join '').Trim()
}
# Lo que haría la API: escribe como plantas_api. Regresa '' si funcionó o el error.
function Como-API([string]$c, [string]$sql) {
    $r = & docker exec $c psql -U postgres -d plantas -X -q -tA -c 'SET ROLE plantas_api' -c 'SET search_path TO app' -c $sql 2>&1 |
         ForEach-Object { "$_" }
    return (($r | Where-Object { $_ -match 'ERROR' }) -join ' ').Trim()
}
function Esperar([string]$c, [string]$sql, [int]$segundos, [string]$que) {
    for ($i = 0; $i -lt $segundos * 2; $i++) {
        if ((Valor $c $sql) -eq 't') { Log "  OK  $que" 'Green'; return }
        Start-Sleep -Milliseconds 500
    }
    Fallar "no pasó en $segundos s: $que"
}

# --- Configuración ----------------------------------------------------
Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*([^#=\s]+)\s*=\s*(.*)$') { Set-Item -Path "env:$($matches[1])" -Value $matches[2] }
}
$escritor = if ($env:ESCRITOR_GLOBALES) { $env:ESCRITOR_GLOBALES } else { 'norte' }
# Víctima: un nodo que NO sea el escritor de las globales (eso es D-01 §10).
$victima = if ($escritor -ne 'centro') { 'centro' } else { 'sur' }
$region  = @{ norte = 1; centro = 2; sur = 3 }[$victima]
$copia   = @{ norte = 'centro'; centro = 'sur'; sur = 'norte' }[$victima]
$tercero = @{ norte = 'sur'; centro = 'norte'; sur = 'centro' }[$victima]
$estado  = @{ 1 = 8; 2 = 22; 3 = 31 }[$region]          # Chihuahua, Querétaro, Yucatán
$cV = "pg-$victima"; $cC = "pg-$copia"; $cT = "pg-$tercero"
$subsVictima = "'sub_frag_r$(@{ norte = 3; centro = 1; sur = 2 }[$victima])','sub_fijos_$victima','sub_glob_$victima'"
$envFailover = @('-e', 'NODO_NORTE_HOST=pg-norte', '-e', 'NODO_CENTRO_HOST=pg-centro', '-e', 'NODO_SUR_HOST=pg-sur',
                 '-e', "PGPASSWORD=$env:POSTGRES_PASSWORD", '-e', "PG_PASS_REPLICA=$env:PG_PASS_REPLICA",
                 '-e', "ESCRITOR_GLOBALES=$escritor")

function Usuario([string]$id, [string]$nombre) {
    return "INSERT INTO usuario (region_id, usuario_id, nombre, apellidos, correo, password_hash, estado_id) " +
           "VALUES ($region, '$id', '$nombre', 'A12', '$($id.Substring(30))@ejemplo.com', repeat('x', 64), $estado)"
}
function Existe([string]$id) { return "SELECT EXISTS (SELECT 1 FROM app.usuario_r$region WHERE usuario_id = '$id')" }

function Instalar {
    Log '>>> Reinstalando el laboratorio limpio (iniciar_lab.ps1)...' 'Cyan'
    & powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'iniciar_lab.ps1') | Out-Null
    if ($LASTEXITCODE -ne 0) { Fallar 'iniciar_lab.ps1 falló; córrelo solo para ver el error.' }
    Log '    laboratorio listo (A9 y A11 en OK)'
}
function Guardar-Logs([string]$desde) {
    foreach ($n in 'norte', 'centro', 'sur') {
        $archivo = Join-Path $raiz "docs\evidencias\a12_logs_$n.txt"
        & docker logs --since $desde "pg-$n" 2>&1 | ForEach-Object { "$_" } | Add-Content -Path $archivo -Encoding UTF8
    }
}
foreach ($n in 'norte', 'centro', 'sur') {
    Set-Content -Path (Join-Path $raiz "docs\evidencias\a12_logs_$n.txt") -Value "Logs de pg-$n durante el ensayo de A12" -Encoding UTF8
}

Log "Topología: '$victima' (región $region) cae; su copia es '$copia'; tercer nodo '$tercero'; escritor de globales '$escritor'." 'Cyan'

# =====================================================================
# ESCENARIO 1 · PÉRDIDA DE NODO
# =====================================================================
Instalar
$inicio = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
Log '=== ESCENARIO 1: pérdida de nodo ===' 'Yellow'

Log "1. La API escribe en '$victima' (región $region)."
$e = Como-API $cV (Usuario 'a1200000-0000-0000-0000-000000000001' 'AntesDeLaCaida')
if ($e) { Fallar "no se pudo escribir en $victima : $e" }
Esperar $cC (Existe 'a1200000-0000-0000-0000-000000000001') 15 "el dato llegó a la copia en '$copia'"

Log "2. Antes de promover, '$copia' NO acepta escrituras de la región ${region}:"
$e = Como-API $cC (Usuario 'a1200000-0000-0000-0000-0000000000ff' 'NoDebeEntrar')
if ($e -notmatch 'row-level security') { Fallar "'$copia' aceptó una escritura de la región $region antes de promover" }
Log "  OK  rechazada por RLS: $e" 'Green'

Log "3. Se APAGA '$victima' (docker stop)."
Docker-Log @('stop', $cV) | Out-Null

Log "4. promover.sh $victima (desde '$copia'):"
if ((Docker-Log (@('exec') + $envFailover + @($cC, 'bash', '/tmp/db/failover/promover.sh', $victima))) -ne 0) { Fallar 'promover.sh falló' }

Log "5. Ahora '$copia' sí acepta escrituras de la región ${region}:"
$e = Como-API $cC (Usuario 'a1200000-0000-0000-0000-000000000002' 'DuranteLaCaida')
if ($e) { Fallar "'$copia' no aceptó la escritura después de promover: $e" }
Log '  OK  escritura aceptada' 'Green'

Log "6. Se ENCIENDE '$victima' otra vez (docker start)."
Docker-Log @('start', $cV) | Out-Null
$i = 0
do { Start-Sleep 1; & docker exec $cV pg_isready -q -U postgres | Out-Null; $i++ } while ($LASTEXITCODE -ne 0 -and $i -lt 30)

Log "7. reincorporar.sh $victima (desde '$copia'):"
if ((Docker-Log (@('exec') + $envFailover + @($cC, 'bash', '/tmp/db/failover/reincorporar.sh', $victima))) -ne 0) { Fallar 'reincorporar.sh falló' }

Log "8. Comprobaciones en '$victima' (ahora copia):"
Esperar $cV (Existe 'a1200000-0000-0000-0000-000000000002') 15 "'$victima' recibió lo que se escribió durante la caída"
$e = Como-API $cV (Usuario 'a1200000-0000-0000-0000-0000000000fe' 'NoDebeEntrar')
if ($e -notmatch 'row-level security|read-only') { Fallar "'$victima' aceptó una escritura de la API siendo copia" }
Log "  OK  '$victima' ya no acepta escrituras de la API: $e" 'Green'
Guardar-Logs $inicio

# =====================================================================
# ESCENARIO 2 · PARTICIÓN DE RED
# =====================================================================
Instalar
$inicio = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
Log '=== ESCENARIO 2: partición de red ===' 'Yellow'

Log "1. La API escribe en '$victima' (región $region)."
$e = Como-API $cV (Usuario 'a1200000-0000-0000-0000-000000000011' 'AntesDeLaParticion')
if ($e) { Fallar "no se pudo escribir en $victima : $e" }
Esperar $cC (Existe 'a1200000-0000-0000-0000-000000000011') 15 "el dato llegó a la copia en '$copia'"

Log "2. Se AÍSLA '$victima' de la red (docker network disconnect); sigue encendido."
Docker-Log @('network', 'disconnect', 'plantas-lab', $cV) | Out-Null

Log "3. Un cliente le escribe a '$victima' aislado (esto no debe sobrevivir):"
$r = Valor $cV "INSERT INTO app.usuario (region_id, usuario_id, nombre, apellidos, correo, password_hash, estado_id) VALUES ($region, 'a1200000-0000-0000-0000-0000000000aa', 'EscritoAislado', 'A12', 'aislado@ejemplo.com', repeat('x', 64), $estado) RETURNING 'escrito'"
Log "    en '$victima' aislado: $r"

Log "4. Esperando a que '$tercero' detecte el corte (wal_sender_timeout = 15 s)..."
Esperar $cT "SELECT count(*) = 0 FROM pg_stat_replication WHERE application_name IN ($subsVictima)" 60 "'$tercero' ya no ve a '$victima' conectado"

Log "5. promover.sh $victima (desde '$copia'):"
if ((Docker-Log (@('exec') + $envFailover + @($cC, 'bash', '/tmp/db/failover/promover.sh', $victima))) -ne 0) { Fallar 'promover.sh falló' }

Log "6. '$copia' escribe la región $region durante la partición:"
$e = Como-API $cC (Usuario 'a1200000-0000-0000-0000-000000000012' 'DuranteLaParticion')
if ($e) { Fallar "'$copia' no aceptó la escritura: $e" }
Log '  OK  escritura aceptada' 'Green'

Log "7. Se REPARA la red (docker network connect)."
Docker-Log @('network', 'connect', 'plantas-lab', $cV) | Out-Null
Start-Sleep 3

Log "8. reincorporar.sh $victima (desde '$copia'):"
if ((Docker-Log (@('exec') + $envFailover + @($cC, 'bash', '/tmp/db/failover/reincorporar.sh', $victima))) -ne 0) { Fallar 'reincorporar.sh falló' }

Log '9. Comprobaciones:'
Esperar $cV (Existe 'a1200000-0000-0000-0000-000000000012') 15 "'$victima' recibió lo que '$copia' escribió durante la partición"
if ((Valor $cV (Existe 'a1200000-0000-0000-0000-0000000000aa')) -ne 'f') { Fallar "la escritura aislada sigue en '$victima'" }
Log "  OK  la escritura hecha en '$victima' aislado se descartó (RPO declarado en D-01 §8)" 'Green'
if ((Valor $cC (Existe 'a1200000-0000-0000-0000-0000000000aa')) -ne 'f') { Fallar "la escritura aislada llegó a '$copia'" }
Log "  OK  la escritura aislada nunca llegó a '$copia': no hubo dos primarios escribiendo la misma región" 'Green'
Guardar-Logs $inicio

Log '=== ENSAYO DE A12 COMPLETO: los 2 escenarios pasaron ===' 'Green'
Log "Evidencias: docs\evidencias\a12_ensayo.txt y a12_logs_<nodo>.txt"
