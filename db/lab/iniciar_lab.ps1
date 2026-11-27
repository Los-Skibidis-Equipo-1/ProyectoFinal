# =====================================================================
# Laboratorio local de 3 nodos: levanta los contenedores, instala la base
# en cada uno con su región (A9) y monta la replicación del anillo y de
# las tablas globales (A11). Al final corre las pruebas y guarda evidencias.
#
# Uso (desde la raíz del repo, en PowerShell, con Docker Desktop abierto):
#   powershell -ExecutionPolicy Bypass -File db\lab\iniciar_lab.ps1
#
# Necesita en .env: POSTGRES_PASSWORD, PG_PASS_ADMIN, PG_PASS_API,
# PG_PASS_REPORTES y PG_PASS_REPLICA.
# Opcionales: ESCRITOR_GLOBALES (norte por defecto; D-01 §4) y
# NODO_NORTE_HOST / NODO_CENTRO_HOST / NODO_SUR_HOST (en el laboratorio
# son los nombres de los contenedores; en las 3 computadoras serán las
# IP de la VPN).
#
# Evidencias: docs\evidencias\a9_pruebas_<nodo>.txt y a11_pruebas_replicacion.txt
# Responsable: Alexa Yalee Sánchez Tejeda · IA: generado y revisado (Claude)
# =====================================================================

$ErrorActionPreference = 'Continue'
$raiz = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$envFile = Join-Path $raiz '.env'

function Fallar($mensaje) {
    Write-Host "ERROR: $mensaje" -ForegroundColor Red
    exit 1
}

# Corre psql dentro de un contenedor; si falla, muestra la salida y se detiene.
function Ejecutar-Psql {
    param([string]$Contenedor, [string]$Descripcion, [string[]]$Parametros)
    $salida = & docker exec -e PGOPTIONS='-c client_min_messages=warning' $Contenedor `
        psql -U postgres -d plantas -q -v ON_ERROR_STOP=1 @Parametros 2>&1
    if ($LASTEXITCODE -ne 0) {
        $salida | ForEach-Object { Write-Host "   $_" }
        Fallar "$Descripcion falló en $Contenedor"
    }
}

# --- 1. Leer .env -----------------------------------------------------
if (-not (Test-Path $envFile)) { Fallar "no existe $envFile (cópialo de .env.example y pon tus contraseñas)" }
Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*([^#=\s]+)\s*=\s*(.*)$') { Set-Item -Path "env:$($matches[1])" -Value $matches[2] }
}
foreach ($v in 'POSTGRES_PASSWORD', 'PG_PASS_ADMIN', 'PG_PASS_API', 'PG_PASS_REPORTES', 'PG_PASS_REPLICA') {
    if (-not (Get-Item "env:$v" -ErrorAction SilentlyContinue)) { Fallar "falta $v en .env" }
}
$escritor = if ($env:ESCRITOR_GLOBALES) { $env:ESCRITOR_GLOBALES } else { 'norte' }
if ($escritor -notin 'norte', 'centro', 'sur') { Fallar "ESCRITOR_GLOBALES debe ser norte, centro o sur" }
$hostNorte  = if ($env:NODO_NORTE_HOST)  { $env:NODO_NORTE_HOST }  else { 'pg-norte' }
$hostCentro = if ($env:NODO_CENTRO_HOST) { $env:NODO_CENTRO_HOST } else { 'pg-centro' }
$hostSur    = if ($env:NODO_SUR_HOST)    { $env:NODO_SUR_HOST }    else { 'pg-sur' }
$hosts = @("host_norte=$hostNorte", "host_centro=$hostCentro", "host_sur=$hostSur")

$nodos = @(
    @{ Contenedor = 'pg-norte';  Nombre = 'norte';  Region = 1 },
    @{ Contenedor = 'pg-centro'; Nombre = 'centro'; Region = 2 },
    @{ Contenedor = 'pg-sur';    Nombre = 'sur';    Region = 3 }
)

# --- 2. Levantar los 3 nodos y copiarles los scripts ----------------
Write-Host '== Levantando pg-norte, pg-centro y pg-sur...' -ForegroundColor Cyan
docker compose -f (Join-Path $PSScriptRoot 'docker-compose.yml') --env-file $envFile up -d --wait
if ($LASTEXITCODE -ne 0) { Fallar 'docker compose no pudo levantar los nodos (¿Docker Desktop está abierto?)' }

foreach ($n in $nodos) {
    docker exec $n.Contenedor rm -rf /tmp/db | Out-Null
    docker cp (Join-Path $raiz 'db') "$($n.Contenedor):/tmp/" | Out-Null
    if ($LASTEXITCODE -ne 0) { Fallar "no se pudo copiar db\ a $($n.Contenedor)" }
}

# --- 3. Quitar la replicación anterior (dos vueltas; ver 00) --------
Write-Host '== Limpiando replicación anterior...' -ForegroundColor Cyan
foreach ($vuelta in 1, 2) {
    foreach ($n in $nodos) {
        Ejecutar-Psql $n.Contenedor '00_limpiar_replicacion.sql' @('-f', '/tmp/db/00_limpiar_replicacion.sql')
    }
}

# --- 4. Instalar 01 a 08 en cada nodo --------------------------------
foreach ($n in $nodos) {
    $c = $n.Contenedor
    Write-Host "== Instalando en $c (región $($n.Region))" -ForegroundColor Cyan
    foreach ($s in '01_esquema', '02_datos_base', '03_indices', '04_funciones', '05_triggers') {
        Ejecutar-Psql $c "$s.sql" @('-f', "/tmp/db/$s.sql")
    }
    Ejecutar-Psql $c '06_roles.sql' @('-v', "pass_admin=$env:PG_PASS_ADMIN", '-v', "pass_api=$env:PG_PASS_API",
                                      '-v', "pass_reportes=$env:PG_PASS_REPORTES", '-f', '/tmp/db/06_roles.sql')
    Ejecutar-Psql $c '07_fragmentacion.sql' @('-v', "region=$($n.Region)", '-f', '/tmp/db/07_fragmentacion.sql')
    Ejecutar-Psql $c '08_rls_replicacion.sql' @('-v', "escritor=$escritor", '-v', "pass_replica=$env:PG_PASS_REPLICA",
                                                '-f', '/tmp/db/08_rls_replicacion.sql')
}

# --- 5. Publicaciones en los 3 y después suscripciones en los 3 -----
Write-Host "== Replicación: anillo Norte -> Centro -> Sur -> Norte; escritor de las globales: $escritor" -ForegroundColor Cyan
foreach ($n in $nodos) {
    Ejecutar-Psql $n.Contenedor '09_publicaciones.sql' @('-v', "escritor=$escritor", '-f', '/tmp/db/09_publicaciones.sql')
}
foreach ($n in $nodos) {
    $p = @('-v', "escritor=$escritor", '-v', "pass_replica=$env:PG_PASS_REPLICA")
    foreach ($h in $hosts) { $p += @('-v', $h) }
    $p += @('-f', '/tmp/db/10_suscripciones.sql')
    Ejecutar-Psql $n.Contenedor '10_suscripciones.sql' $p
}

# --- 6. Pruebas y evidencias -----------------------------------------
Write-Host '== Pruebas' -ForegroundColor Cyan
foreach ($n in $nodos) {
    $c = $n.Contenedor
    $evidencia = Join-Path $raiz "docs\evidencias\a9_pruebas_$($n.Nombre).txt"
    docker exec $c sh -c "psql -U postgres -d plantas -f /tmp/db/tests/a9_pruebas_fragmentacion.sql > /tmp/a9.txt 2>&1"
    docker cp "${c}:/tmp/a9.txt" $evidencia | Out-Null
    $ok = (Select-String -Path $evidencia -Pattern 'OK    ').Count
    $fallo = (Select-String -Path $evidencia -Pattern 'FALLO|ERROR').Count
    if ($fallo -gt 0 -or $ok -ne 22) { Fallar "A9 en $c : $ok OK y $fallo errores (revisa $evidencia)" }
    Write-Host "   A9  $c : $ok pruebas OK" -ForegroundColor Green
}

# A11 se corre una vez y se conecta a los 3 nodos.
$evidencia = Join-Path $raiz 'docs\evidencias\a11_pruebas_replicacion.txt'
$vars = "-v escritor=$escritor -v host_norte=$hostNorte -v host_centro=$hostCentro -v host_sur=$hostSur"
docker exec -e "PGPASSWORD=$env:POSTGRES_PASSWORD" pg-norte sh -c `
    "psql -U postgres -d plantas $vars -f /tmp/db/tests/a11_pruebas_replicacion.sql > /tmp/a11.txt 2>&1"
docker cp 'pg-norte:/tmp/a11.txt' $evidencia | Out-Null
$esperadas = if ($escritor -eq 'centro') { 27 } else { 28 }
$ok = (Select-String -Path $evidencia -Pattern 'OK    ').Count
$fallo = (Select-String -Path $evidencia -Pattern 'FALLO|ERROR').Count
if ($fallo -gt 0 -or $ok -ne $esperadas) { Fallar "A11: $ok de $esperadas OK y $fallo errores (revisa $evidencia)" }
Write-Host "   A11 entre los 3 nodos: $ok pruebas OK" -ForegroundColor Green

Write-Host ''
Write-Host 'Listo: 3 nodos instalados, cada uno con su región, y la replicación funcionando.' -ForegroundColor Green
Write-Host 'Conexión desde tu computadora: localhost:5441 (Norte), 5442 (Centro), 5443 (Sur).'
Write-Host 'Para apagar: docker compose -f db\lab\docker-compose.yml --env-file .env down'
