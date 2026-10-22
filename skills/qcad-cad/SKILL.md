---
name: qcad-cad
description: AI-driven 2D CAD with qcad-mcp — DXF/DWG floor plans, SVG preview, STL extrusion, room analysis, QCAD Pro ECMAScript bridge.
---

# qcad-cad skill

## Agent vs human routing

- **Agents**: drive everything through MCP tools (`plan_*`, `qcad_*`) or the
  REST API (`POST /api/v1/control/tool`). Never hand-edit DXF XML.
- **Humans**: use the webapp (port 11967) — Depot, Viewer, Extrude, Analyse,
  Pipeline pages — or QCAD Pro directly for fine drafting.

## Tool catalog (8 portmanteaus + 4 cards, verified against src/qcad_mcp/tools/portmanteau.py)

Core ezdxf (no QCAD Pro needed):
`plan(op="info"|"to_svg"|"extrude"|"stack"|"obj"|"glb"|"drawings"|"export"|"analyse"|"create"|"depot", ...)`
Edits: `plan_edit(op="convert"|"modify", ...)`.
BIM/analysis: `plan_bim(op="auto_dimension"|"building_meta"|"to_ifc_data", ...)`,
`plan_annotate(op="wall_data"|"beam_analysis"|..., ...)`.
QCAD Pro 3.x: `qcad(op="status")`, `plan_pro(op="script"|"render"|"exec", ...)`,
`plan_annotate(op="dimension"|"measure"|"text"|"hatch"|"block_insert"|"array", ...)`.
Libraries: `plan_library(op="blocks"|"blocks_download"|"scripts_search"|"scripts_download", ...)`.
Agentic: `plan_ai(op="generate"|"agentic"|"transpile"|"sampling", ...)`.
Meta: `qcad(op="help"|"shutdown")`, `show_qcad_status_card`,
`show_depot_card`, `show_beam_analysis_card`, `show_building_meta_card`.
Resources: `cad://depot`, `cad://depot/{filename}`. Prompts: 3 registered
in agentic_tools (`@mcp.prompt()`).

Always call `qcad(op="status")` first when a workflow needs QCAD Pro — every Pro
tool degrades or fails without it.

## Workflow 1 — floor plan to 3D print

1. `plan(op="depot")` → pick the DXF (or `plan(op="create")` from primitives).
2. `plan(op="info", file_name=...)` → confirm wall layers exist.
3. `plan(op="to_svg", file_name=...)` → visual sanity check of walls/openings.
4. `plan(op="analyse", file_name=...)` → rooms, areas, doors/windows.
5. `plan(op="extrude", file_name=..., wall_height=3.0, wall_thickness=0.3)` → STL.
6. Ship the STL to freecad-mcp (`POST /api/v1/freecad/solid`) for solid work.

## Workflow 2 — annotate an existing drawing (QCAD Pro)

1. `qcad(op="status")` → installed + running must both be true.
2. `plan_annotate(op="dimension"|"text"|"hatch", ...)` with explicit coordinates.
3. `plan_pro(op="render", file_name=..., output_name="proof.pdf")` → high-fidelity proof.
4. Never invent coordinates — read them from `plan_annotate(op="measure", ...)` or `plan(op="info")`
   bounding boxes first.

## Config

- Backend 11966, frontend 11967. Env: `QCAD_MCP_DEPOT`, `QCAD_MCP_OUTPUT`,
  `QCAD_PRO_PATH`, `MCP_BRIDGE_URLS`, `FREECAD_MCP_URL`.
- Dual transport: `--mode stdio` (Claude Desktop), `--mode http` (webapp),
  `--mode dual`. Under `QCAD_TAURI=1` stdio is forced to http.

## Troubleshooting

- QCAD Pro tools fail → `qcad(op="status")`; check `QCAD_PRO_PATH`, start QCAD GUI.
- Empty STL → wall-layer auto-detect missed: pass `wall_layers` explicitly
  (names containing wall/mauer/wand/mur/parete/pared).
- DWG input without QCAD Pro → convert impossible; ezdxf reads DXF only.
- Live multi-document bridge (issue #1) is macOS-only proposal, deferred —
  see docs/live-bridge-proposal.md.
