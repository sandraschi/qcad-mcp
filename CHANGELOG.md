# Changelog

All notable changes to the QCAD MCP server and webapp.

## [0.3.0] - 2026-05-13

### Added

- **`plan_measure`**: precise distance/angle/area/perimeter measurement via QCAD Pro geometry engine.
- **`plan_text`**: add text annotations (RTextEntity) with height, alignment, rotation, bold/italic.
- **`plan_hatch`**: add hatch/fill patterns (ANSI31-38, AR-CONC, SOLID, EARTH, etc.) to closed polygon regions.
- **`plan_dimension`**: add aligned, radial, diametric, angular, rotated dimensions.
- **`plan_agentic`**: natural language CAD goal → ECMAScript code generation + execution. Template fallback when no AI sampling.

### Changed

- **Lint zeroed**: biome 141→0 (formatting, `any`→typed interfaces, a11y keyboard handlers, label associations, import ordering). tsc 32→0 (proper interfaces for all API responses).
- `plan_exec` uses headless autostart instead of non-functional `-exec` flag.
- `exec_in_live` returns raw `stdout` for custom marker extraction.

### Fixed

- `plan_measure` entity type detection: `instanceof` checks instead of string comparison.
- `plan_hatch` uses constructor-based `RHatchData()` — setter methods unavailable in QCAD 3.32.9.
- Total MCP tools: 11 → 17 → 20.

## [0.2.0] - 2026-05-12

### Added

- **QCAD Pro ECMAScript bridge** (`plan_script`): execute arbitrary ECMAScript against DXF documents via QCAD Pro headless mode.
- **High-fidelity rendering** (`plan_render`): SVG/PDF/BMP via QCAD Pro's native engine.
- **QCAD Pro status** (`qcad_status`): detect installation, running state, version.
- **Live instance control** (`plan_exec`): execute ECMAScript in temporary QCAD Pro session.
- **Service layer**: `src/qcad_mcp/services/qcad_pro.py`.
- `plan_export` now tries QCAD Pro first for SVG/PDF, falling back to ezdxf+matplotlib.
- REST endpoint `GET /api/v1/status`.

## [0.1.0] - 2026-05-12

### Added

- Initial release: FastMCP 3.2 server, Vite/React dashboard, 7 core MCP tools, depot CRUD, SSE log stream.
