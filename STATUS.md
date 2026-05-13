# Status — qcad-mcp

**Status**: v0.3.0 — 20 tools, zero lint errors across all layers.

**Repo**: `D:\Dev\repos\qcad-mcp`
**Ports**: Backend 10966, Frontend 10967

## Architecture

DXF/DWG floor plans → SVG preview + STL extrusion + ECMAScript bridge → Resonite/Unity3D worlds.

Core engine: `ezdxf` (pure Python, MIT, free). QCAD Pro (€42, Swiss-made) enables ECMAScript scripting bridge, high-fidelity rendering, live instance control.

See `ARCHITECTURE.md` for full design.

## Implemented

- FastMCP 3.2 server with 20 tools: plan_info, plan_to_svg, plan_extrude, plan_export, plan_analyse, plan_create, plan_depot, plan_convert, plan_modify, plan_blocks, plan_blocks_download, qcad_status, plan_script, plan_render, plan_exec, plan_dimension, plan_agentic, plan_measure, plan_text, plan_hatch
- QCAD Pro ECMAScript bridge: execute arbitrary scripts against DXF documents headlessly
- QCAD Pro high-fidelity rendering: native SVG/PDF/BMP via dwg2* tools
- Live instance control: push ECMAScript to running QCAD Pro GUI
- Service layer: `src/qcad_mcp/services/qcad_pro.py`
- Fleet-standard Vite + React webapp (12 pages)
- REST API with 20+ endpoints
- SSE log stream, LLM chat endpoint, settings persistence
- justfile with bootstrap, serve, web, lint, fix, test, check
- Lint: ruff 0, biome 0, tsc 0 errors
