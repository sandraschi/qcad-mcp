# start.ps1 — QCAD MCP + Webapp
$WebPort = 10967
$ApiPort = 10966

# Kill any existing processes on these ports
Get-NetTCPConnection -LocalPort $ApiPort -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
Get-NetTCPConnection -LocalPort $WebPort -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 1

# Start backend (dual mode: REST + MCP SSE)
$env:QCAD_MCP_WORK_DIR = "$env:TEMP\qcad_mcp_work"
$job = Start-Job -Name "qcad-mcp" -ScriptBlock {
    Set-Location "$using:PWD"
    uv run python -m qcad_mcp.server --mode dual --port $using:ApiPort
}
Start-Sleep -Seconds 3

# Start webapp
Push-Location webapp
Start-Process cmd -ArgumentList "/c", "npm", "run", "dev"
Pop-Location

Start-Sleep -Seconds 5
Write-Host "QCAD MCP:    http://localhost:$ApiPort/api/v1/status" -ForegroundColor Green
Write-Host "Webapp:      http://localhost:$WebPort" -ForegroundColor Green
Write-Host "MCP SSE:     http://localhost:$ApiPort/sse" -ForegroundColor Green
Write-Host ""
Write-Host "Opening webapp in default browser..." -ForegroundColor Cyan
Start-Process "http://localhost:$WebPort"
