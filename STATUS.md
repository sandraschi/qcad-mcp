# Status — qcad-mcp

**Status**: v0.1.0 — Implemented and operational.

**Repo**: `D:\Dev\repos\qcad-mcp`
**Ports**: Backend 10966, Frontend 10967

## Architecture

DXF/DWG floor plans → SVG preview + STL extrusion → Resonite/Unity3D worlds.

Core engine: `ezdxf` (pure Python, MIT, free). QCAD Pro (€50.40, Swiss-made) optional for DWG + high-fidelity PDF.

See `ARCHITECTURE.md` for full design.

## Implemented

- FastMCP 3.2 server with 5 tools: plan_info, plan_to_svg, plan_extrude, plan_export, plan_analyse
- Fleet-standard Vite + React webapp (Dashboard, Viewer, Extrude, Analyse, Models, Logs, Settings, Help)
- REST API: `/api/v1/status`, `/api/v1/upload`, `/api/v1/download/{name}`, `/api/v1/files`, `/api/v1/control/tool`
- SSE log stream, LLM chat endpoint, settings persistence
- justfile with bootstrap, serve, web, lint, fix, test, check

## Next Steps

- Test with real DXF floor plans
- Add sample DXF files to tests/
- Register in fleet port registry (WEBAPP_PORTS.md)
