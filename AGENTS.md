# qcad-mcp — Agent Guide

## Overview
QCAD MCP server — DXF/DWG floor plans to SVG preview + STL extrusion via MCP tools and REST API

## Ports
- Backend: **11966** (FastAPI + MCP HTTP `/mcp`)
- Frontend: **11967** (Vite React SPA)

## Key Commands
- `just serve` — start backend (dual transport)
- `start.ps1` — start backend + frontend + open browser
- `just test` — run pytest + Playwright e2e
- `just lint` — ruff + biome + tsc

## Standards
- FastMCP 3.4+ portmanteau tool pattern with annotation constants
- Structured dict returns with `success`, `message`, `data`
- Dual transport: stdio (Claude Desktop) + HTTP (`MCP_TRANSPORT=http`)
- See mcp-central-docs for fleet-wide coding standards

## Key Files
- `README.md` — full documentation including pricing model
- `pyproject.toml` — build config and entry points
- `CLAUDE.md` — Claude Code context
- `webapp/src/pages/` — 16 React pages (Dashboard, Demo, Depot, Viewer, etc.)

