# Fleet: mcp-central-docs/templates/pre-commit-biome.ps1
# Copy to {repo}/scripts/pre-commit-biome.ps1 - used by .pre-commit-config.yaml local hook.
# Detects the web root (webapp/ canonical, then legacy variants), ensures
# node_modules, runs npm run biome:ci.

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

$webRoot = $null
foreach ($candidate in @("webapp", "webapp/frontend", "web_sota", "web-sota", "web", "frontend", "ui", "web_app")) {
    $path = Join-Path $repoRoot $candidate
    if (Test-Path (Join-Path $path "package.json")) {
        $webRoot = $path
        break
    }
}

if (-not $webRoot) {
    exit 0
}

Push-Location $webRoot
try {
    if (Get-Command bun -ErrorAction SilentlyContinue) {
        if (-not (Test-Path "node_modules")) {
            bun install --frozen-lockfile 2>$null
            if ($LASTEXITCODE -ne 0) {
                bun install 2>$null
            }
        }
        bun run biome:ci
        exit $LASTEXITCODE
    }

    if (-not (Test-Path "node_modules")) {
        npm ci --silent
        if ($LASTEXITCODE -ne 0) {
            npm install --silent
        }
    }
    npm run biome:ci
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
