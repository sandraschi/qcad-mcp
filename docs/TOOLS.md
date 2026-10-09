# Tools — qcad-mcp (40 MCP tools)

Registered via `register(mcp)` in `src/qcad_mcp/tools/*.py`. Full signatures
in `llms-full.txt`. `qcad_help` prints this catalog live.

## Core — ezdxf, no QCAD Pro (13)

| Tool | Purpose |
|---|---|
| `plan_info` | DXF metadata: layers, entity counts, bbox, blocks |
| `plan_to_svg` | DXF → SVG preview, layer filter, background |
| `plan_extrude` | Wall LINE/LWPOLYLINE → 3D STL (h=3.0 m, t=0.3 m defaults) |
| `plan_stack` | Multi-storey extrusion |
| `plan_obj` / `plan_glb` | STL → OBJ / GLB shuttle (Resonite path) |
| `plan_drawings` | Drawing set helpers |
| `plan_export` | DXF → SVG/PDF/PNG (Pro first, ezdxf fallback) |
| `plan_analyse` | Rooms, areas, doors/windows |
| `plan_create` | DXF from primitives (line/rect/circle/text/polyline) |
| `plan_depot` | Depot listing with sidecar metadata |
| `plan_convert` | DWG↔DXF via QCAD Pro CLI |
| `plan_modify` | Delete/offset/colour/rename/freeze/lock/merge layers |

## BIM / analysis (5)

`plan_auto_dimension`, `plan_building_meta`, `plan_to_ifc_data`,
`plan_wall_data` (BIM JSON for freecad-mcp), `plan_beam_analysis`
(numpy FEM: moments, shear, deflection).

## QCAD Pro 3.x (10)

`qcad_status`, `plan_script` (arbitrary ECMAScript, 120 s),
`plan_render` (SVG/PDF/BMP), `plan_exec` (snippet, no output file),
`plan_dimension`, `plan_measure`, `plan_text`, `plan_hatch`,
`plan_block_insert`, `plan_array`.

## Libraries (4)

`plan_blocks`, `plan_blocks_download` (4800+ blocks),
`plan_scripts_search`, `plan_scripts_download` (gallery/Gist/bundled).

## Agentic (4)

`plan_generate`, `plan_agentic` (NL → ECMAScript via sampling),
`plan_transpile` (AutoLISP → ECMAScript), `cad_sampling`.

## Meta / cards (4)

`qcad_help` (this catalog), `qcad_shutdown` (orderly exit),
`show_qcad_status_card`, `show_depot_card`, `show_beam_analysis_card`,
`show_building_meta_card` (Prefab UI).

## REST equivalents (selection)

Depot CRUD `/api/v1/depot*`, `/api/v1/upload`, `/api/v1/download/{f}`,
tool bridge `/api/v1/control/tool`, chat `/api/v1/chat` + `/api/llm/chat`,
LLM `/api/llm/providers|models|gpus|loaded|discover|onboarding`,
skills `/api/skills`, diagnostics `/api/v1/diagnostics`,
health `/api/v1/health|/status`, shutdown `POST /api/shutdown`.
