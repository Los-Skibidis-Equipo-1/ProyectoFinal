# =====================================================================
# Laboratorio local de 3 nodos: levanta los contenedores e instala la
# base en cada uno con su región (A9).
#
# Uso (desde la raíz del repo, en PowerShell):
#   powershell -ExecutionPolicy Bypass -File db\lab\iniciar_lab.ps1
#
# Necesita en .env: POSTGRES_PASSWORD, PG_PASS_ADMIN, PG_PASS_API, PG_PASS_REPORTES.
# Deja las evidencias en docs\evidencias\a9_pruebas_<nodo>.txt
# Responsable: Alexa Yalee Sánchez Tejeda · IA: generado y revisado (Claude)
# =====================================================================

$ErrorActionPreference = 'Continue'
$raiz = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$envFile = Join-Path $raiz '.env'

function Fallar($mensaje) {
    Write-Host "ERROR: $mensaje" -ForegroundColor Red
    exit 1
}

# --- 1. Leer .env -----------------------------------------------------
if (-not (Test-Path $envFile)) { Fallar "no existe $envFile (cópialo de .env.example y pon tus contraseñas)" }
Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*([^#=\s]+)\s*=\s*(.*)$') { Set-Item -Path "env:$($matches[1])" -Value $matches[2] }
}
foreach ($v in 'POSTGRES_PASSWORD', 'PG_PASS_ADMIN', 'PG_PASS_API', 'PG_PASS_REPORTES') {
    if (-not (Get-Item "env:$v" -ErrorAction SilentlyContinue)) { Fallar "falta $v en .env" }
}

# --- 2. Levantar los 3 nodos y esperar a que estén listos ------------
Write-Host '== Levantando pg-norte, pg-centro y pg-sur...' -ForegroundColor Cyan
docker compose -f (Join-Path $PSScriptRoot 'docker-compose.yml') --env-file $envFile up -d --wait
if ($LASTEXITCODE -ne 0) { Fallar 'docker compose no pudo levantar los nodos (¿Docker Desktop está abierto?)' }

# --- 3. Instalar en cada nodo ----------------------------------------
$nodos = @(
    @{ Contenedor = 'pg-norte';  Nombre = 'norte';  Region = 1 },
    @{ Contenedor = 'pg-centro'; Nombre = 'centro'; Region = 2 },
    @{ Contenedor = 'pg-sur';    Nombre = 'sur';    Region = 3 }
)

foreach ($n in $nodos) {
    $c = $n.Contenedor
    Write-Host "== $c (región $($n.Region))" -ForegroundColor Cyan

    docker exec $c rm -rf /tmp/db | Out-Null
    docker cp (Join-Path $raiz 'db') "${c}:/tmp/" | Out-Null
    if ($LASTEXITCODE -ne 0) { Fallar "no se pudo copiar db\ a $c" }

    # Scripts 01 a 05 (los NOTICE se ocultan para que la salida sea legible).
    foreach ($s in '01_esquema', '02_datos_base', '03_indices', '04_funciones', '05_triggers') {
        docker exec -e PGOPTIONS='-c client_min_messages=warning' $c `
            psql -U postgres -d plantas -q -v ON_ERROR_STOP=1 -f "/tmp/db/$s.sql" | Out-Null
        if ($LASTEXITCODE -ne 0) { Fallar "$s.sql falló en $c" }
    }

    # 06: roles (contraseñas desde .env).
    docker exec -e PGOPTIONS='-c client_min_messages=warning' $c `
        psql -U postgres -d plantas -q -v ON_ERROR_STOP=1 `
        -v "pass_admin=$env:PG_PASS_ADMIN" -v "pass_api=$env:PG_PASS_API" -v "pass_reportes=$env:PG_PASS_REPORTES" `
        -f /tmp/db/06_roles.sql | Out-Null
    if ($LASTEXITCODE -ne 0) { Fallar "06_roles.sql falló en $c" }

    # 07: fragmentación con la región de este nodo.
    docker exec $c psql -U postgres -d plantas -q -v ON_ERROR_STOP=1 -v "region=$($n.Region)" `
        -f /tmp/db/07_fragmentacion.sql | Out-Null
    if ($LASTEXITCODE -ne 0) { Fallar "07_fragmentacion.sql falló en $c" }

    # Pruebas de A9 y evidencia.
    $evidencia = Join-Path $raiz "docs\evidencias\a9_pruebas_$($n.Nombre).txt"
    docker exec $c sh -c "psql -U postgres -d plantas -f /tmp/db/tests/a9_pruebas_fragmentacion.sql > /tmp/a9.txt 2>&1"
    docker cp "${c}:/tmp/a9.txt" $evidencia | Out-Null
    $ok = (Select-String -Path $evidencia -Pattern 'OK    ').Count
    $fallo = (Select-String -Path $evidencia -Pattern 'FALLO|ERROR').Count
    if ($fallo -gt 0 -or $ok -ne 22) {
        Fallar "$c : $ok OK y $fallo errores (revisa $evidencia)"
    }
    Write-Host "   $ok pruebas OK -> $evidencia" -ForegroundColor Green
}

Write-Host ''
Write-Host 'Listo: los 3 nodos tienen la base instalada y cada uno conoce su región.' -ForegroundColor Green
Write-Host 'Conexión desde tu computadora: localhost:5441 (Norte), 5442 (Centro), 5443 (Sur).'
