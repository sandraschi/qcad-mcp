# Changelog

All notable changes to the QCAD MCP server and webapp.

## [0.2.0] - 2026-05-12

### Added

- **QCAD Pro ECMAScript bridge** (`plan_script`): execute arbitrary ECMAScript against DXF documents via QCAD Pro headless mode. Full access to QCAD API (entities, layers, blocks, geometry).
- **High-fidelity rendering** (`plan_render`): SVG/PDF/BMP output via QCAD Pro's native engine (hatches, TrueType fonts, lineweights, dimensions correctly rendered).
- **QCAD Pro status** (`qcad_status`): detect installation, running state, version.
- **Live instance control** (`plan_exec`): execute ECMAScript in running QCAD Pro GUI for instant visual feedback.
- **Service layer**: `src/qcad_mcp/services/qcad_pro.py` — detection, script execution, rendering, conversion.
- `plan_export` now tries QCAD Pro first for SVG/PDF, falling back to ezdxf+matplotlib.
- REST endpoint `GET /api/v1/status` returns QCAD Pro info.
- Lifespan startup now logs QCAD Pro version and running state.

### Changed

- `_qcad_pro_available()` and `_qcad_pro_convert()` now delegate to the service module.
- Total registered MCP tools: 11 → 15.

## [0.1.0] - 2026-05-12

### Added

- Initial release: FastMCP 3.2 server with SSE transport on port 10966.
- Vite/React dashboard on port 10967 (9 pages: Dashboard, Depot, Viewer, Extrude, Analyse, Models, Logs, Settings, Help).
- MCP tools: `plan_info`, `plan_to_svg`, `plan_extrude`, `plan_export`, `plan_analyse`, `plan_create`, `plan_depot`.
- REST API: `/api/v1/depot` (CRUD), `/api/v1/files`, `/api/v1/upload`, `/api/v1/download`, `/api/v1/control/tool`, `/api/v1/chat`, `/api/v1/settings`.
- DXF→SVG rendering via ezdxf + matplotlib with layer filtering.
- DXF→STL wall extrusion with configurable height/thickness.
- Room detection and area calculation from closed polylines.
- DXF creation from primitives (line, rect, circle, text, polyline).
- Depot management with JSON metadata sidecars.
- Ollama chat integration (CAD Expert, model `gemma3:1b`).
- SSE log stream with 2000-entry ring buffer.
- Fleet-standard start.ps1, justfile, ruff/biome linting.
- Fleet-standard docs hub with 6 linked sub-docs.
- Architecture doc describing the full data pipeline and fleet integration.
