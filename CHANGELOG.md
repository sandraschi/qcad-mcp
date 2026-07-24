# Changelog

All notable changes to the QCAD MCP server and webapp.

## [0.4.0] — 2026-07-24

### Added
- **SOTA annotations**: All 26 tools now have `@mcp.tool(annotations=READ_ONLY/MUTATING)`. Using proper imports from `fastmcp.tool.annotations` instead of legacy dict.
- **llms-full.txt**: Fleet-standard full LLM documentation covering all 26 tools, 3 prompts, 2 resources, architecture, fleet integration, error handling.
- **glama.json**: Glama registry entry with all 26 tools, 3 prompts, 2 resources.
- **`/api/v1/health` endpoint**: Returns QCAD Pro status, ezdxf version, Docker/OpenFOAM/FluidX3D availability, compiler detection, tool count, uptime.
- **PipelinePage**: New 5-step webapp wizard (Describe → View → Analyse → Extrude → FreeCAD pipeline).
- **`STATUS.md`**: Updated to reflect 26 tools, added quality metrics, fleet standards checklist, cross-repo pipeline diagram, short/medium-term roadmap.

### Fixed
- `ctx: None = None` → `ctx: Context = None` in `plan_agentic` and `plan_transpile` (SOTA type hint compliance).
- Duplicate `## Examples` section in `plan_modify` docstring merged.
- `plan_beam_analysis` and `cad_sampling` now correctly annotated `READ_ONLY` (were missing annotations entirely).

### Changed
- `_READ_ONLY = {"readonly": True}` removed from all 5 tool files — replaced with proper `from fastmcp.tool.annotations import READ_ONLY, MUTATING`.
- Total MCP tools: 22 → 26 documented in STATUS.md.

### Added
- **Tool Playground** (`/playground`): API tester page with tool selector, JSON arg editor with templates per tool, depot file-name injector, raw response viewer with copy.
- **Elaborate floorplan presets**: Baroque church (45m nave, apse, transept, 12 columns, 6 chapels), mob compound (walls, towers, villa, pool), art museum (atrium + 4 gallery wings). Plus parametric fallback that parses dimensions/rooms from any text.
- **QCAD Pro panel** on Dashboard: live status, version, install path, quick links to Demo/Playground/Help.
- **Batch STL** on BatchPage: run `plan_extrude` across all depot DXF files, STL gallery with download links.
- **Live FreeCAD panel** on PipelinePage step 5: calls `plan_wall_data`, renders wall segment table, copy-button generates `bim_create_wall(...)` calls.
- **Full REST tool bridge**: All 28 MCP tools now exposed via `/api/v1/control/tool` (previously only 9). Added `plan_blocks`, `plan_blocks_download`, `qcad_status`, `plan_scripts_search`, `plan_scripts_download`, `plan_beam_analysis`, `plan_measure`, `plan_wall_data`, `plan_dimension`, `plan_text`, `plan_hatch`, `plan_block_insert`, `plan_array`, `plan_script`, `plan_render`, `plan_exec`.
- **QCAD Pro auto-start**: Backend launches QCAD Pro GUI on startup via `_ensure_qcad_running()`.
- **Dashboard hero section**: Welcome banner with QCAD Pro status dot, live ezdxf version.
- **Topbar redesign**: Page title, Pop Out and Companion Mode buttons, connection status.
- **Demo page fallback**: AI CAD Demo falls back to `plan_create` geometry when QCAD Pro is unavailable.
- **`[project.scripts]` entry point**: `qcad-mcp = qcad_mcp.server:main`

### Fixed
- **color-scheme:dark** in index.css — white scrollbars and light native form controls fixed.
- **PipelinePage indigo theme** → amber (was a different app colour).
- **FloatingChat cyan theme** → amber, inline SVGs → Lucide icons, "Go" → Send icon.
- **White SVG preview backgrounds** in PipelinePage and DemoPage.
- **Redundant backend status indicators** on Dashboard (removed duplicate dot).
- **Sidebar collapse animation** — text now fades with the width instead of popping.
- **useZoom** CSS fallback: `transform:scale()` → `document.documentElement.style.zoom`.
- **Dashboard QCAD Pro status** now correctly reads nested `qcad_pro.running` from API.
- **Dead imports** removed across 7 pages (8 unused Lucide icons).

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
