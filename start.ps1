param(
    [switch]$Headless,
    [switch]$BackendOnly,
    [switch]$FrontendOnly,
    [switch]$NoBrowser
)

$WebPort = 10967
$ApiPort = 10966
$ProjectRoot = $PSScriptRoot

$FleetStartPath = Join-Path $ProjectRoot "scripts\FleetStartMode.ps1"
if (-not (Test-Path -LiteralPath $FleetStartPath)) {
    Write-Host "ERROR: Missing vendored launcher helper: $FleetStartPath" -ForegroundColor Red
    exit 1
}
. $FleetStartPath
$FleetStart = Initialize-FleetStartMode @PSBoundParameters
Enter-FleetHeadlessConsole -Headless:$Headless -BackendOnly:$BackendOnly
Stop-FleetPortSquatters -Ports @($WebPort, $ApiPort) -Label "qcad-mcp"

if (-not (Assert-FleetPortsAvailable -Ports @($WebPort, $ApiPort) -Label "qcad-mcp")) { exit 1 }

$env:QCAD_MCP_WORK_DIR = "$env:TEMP\qcad_mcp_work"
$backendCmd = "Set-Location '$ProjectRoot'; uv run --project '$ProjectRoot' python -m qcad_mcp.server --mode dual --host 127.0.0.1 --port $ApiPort"
Write-Host "Starting QCAD MCP backend on port $ApiPort ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd -WindowStyle Normal

$healthUrl = "http://127.0.0.1:$ApiPort/api/v1/status"
$attempt = 0
while ($attempt -lt 40) {
    try {
        $null = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
        Write-Host "Backend ready at $healthUrl" -ForegroundColor Green
        break
    } catch {
        Start-Sleep -Seconds 2
        $attempt++
    }
}

if (-not $FleetStart.RunFrontend) {
    while ($true) { Start-Sleep -Seconds 60 }
}

Push-Location (Join-Path $ProjectRoot "webapp")
if (-not (Test-Path "node_modules")) { npm install }
Write-Host "Starting Vite frontend on port $WebPort ..." -ForegroundColor Green
npm run dev -- --port $WebPort --host 127.0.0.1 --strictPort


