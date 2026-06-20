set windows-shell := ["pwsh.exe", "-NoLogo", "-Command"]
import 'scripts/just/fleet.just'

export NAME := "QCAD MCP"
export DESC := "DXF/DWG floor plans to SVG + STL via MCP tools"
export VER  := "0.3.0"
export PORT := "10966"
export HOST := "0.0.0.0"

# Open the interactive recipe dashboard in the browser
default:
    @just --list

# ── Lifecycle ─────────────────────────────────────────────────────────────────

# Synchronise all dependencies and dev extras
bootstrap:
    uv sync --all-extras
    Set-Location '{{justfile_directory()}}\webapp'
    cmd /c npm install

# Workspace sanitisation
clean:
    if (Test-Path -Path "**/__pycache__") { Get-ChildItem -Path "." -Recurse -Filter "__pycache__" | Remove-Item -Recurse -Force }; \
    if (Test-Path -Path ".pytest_cache") { Remove-Item -Recurse -Force ".pytest_cache" }; \
    if (Test-Path -Path "htmlcov") { Remove-Item -Recurse -Force "htmlcov" }

# Complete project re-initialisation
setup: clean bootstrap
    Write-Host "QCAD MCP ready." -ForegroundColor Green

# ── Operation ─────────────────────────────────────────────────────────────────

# Start the QCAD MCP server (Unified Gateway, dual mode)
serve mode="dual" port=PORT:
    uv run python -m qcad_mcp.server --mode {{mode}} --port {{port}}

# Start in stdio mode (for MCP clients)
stdio:
    uv run python -m qcad_mcp.server --mode stdio

# Start the Vite dashboard
web:
    Set-Location '{{justfile_directory()}}\webapp'
    cmd /c npm run dev

# ── Development ───────────────────────────────────────────────────────────────

# Start server with auto-reload
dev port=PORT:
    uv run uvicorn qcad_mcp.server:app --reload --port {{port}} --host {{HOST}}

# ── Quality ───────────────────────────────────────────────────────────────────

# Execute linting (ruff + biome + tsc)
lint:
    uv run ruff check src/
    Set-Location '{{justfile_directory()}}\webapp'
    npx @biomejs/biome ci .
    npx tsc --noEmit

# Execute auto-fixes and formatting
fix:
    uv run ruff check src/ --fix
    uv run ruff format src/
    Set-Location '{{justfile_directory()}}\webapp'
    npx @biomejs/biome check --write .

# Fast quality check (lint + tests)
check: lint test

# ── Testing ───────────────────────────────────────────────────────────────────

# Run the complete test suite
test:
    uv run pytest

# Build an MCPB portable bundle from tool definitions
mcpb-pack:
    uvx mcpb build --server qcad_mcp.server:mcp --output qcad-mcp.mcpb

# Register this MCP server with a client (stdio)
install-mcp:
    uv run python -m qcad_mcp.server --mode stdio

# Regenerate LLM documentation files (llms.txt)
llms-txt:
    uv run python -m qcad_mcp.utils.llms_txt

# ── Diagnostics ───────────────────────────────────────────────────────────────

# Check QCAD MCP status
health:
    curl http://localhost:10966/api/v1/status

# ── Native (Tauri) ────────────────────────────────────────────────────────────

# Build Tauri native desktop app (Rust + WebView2)
build-native:
    Set-Location '{{justfile_directory()}}\native'
    $env:Path = "$env:USERPROFILE\.cargo\bin;$env:Path"
    .\build.ps1

# Run CUA smoke test against installed NSIS app
cua-nsis-test:
    C:\Windows\py.exe scripts/cua-smoke.py

# Build Tauri native app (debug)
build-native-debug:
    Set-Location '{{justfile_directory()}}\native'
    $env:Path = "$env:USERPROFILE\.cargo\bin;$env:Path"
    npx @tauri-apps/cli build --debug

tauri-sidecar:
    pwsh -NoLogo -File '{{justfile_directory()}}\native\build-sidecar.ps1'

tauri-build:
    Set-Location '{{justfile_directory()}}\native'
    $env:Path = "$env:USERPROFILE\.cargo\bin;$env:Path"
    .\build.ps1

tauri-dev:
    Set-Location '{{justfile_directory()}}\native'
    $env:Path = "$env:USERPROFILE\.cargo\bin;$env:Path"
    npm install
    npx @tauri-apps/cli dev
