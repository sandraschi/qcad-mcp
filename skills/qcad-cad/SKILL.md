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

## Tool catalog (40 ops, all verified against src/qcad_mcp/tools/)

Core engine ezdxf (no QCAD Pro needed):
`plan_info`, `plan_to_svg`, `plan_extrude`, `plan_stack`, `plan_obj`,
`plan_glb`, `plan_drawings`, `plan_export`, `plan_analyse`, `plan_create`,
`plan_depot`, `plan_convert`, `plan_modify`.
BIM/analysis: `plan_auto_dimension`, `plan_building_meta`, `plan_to_ifc_data`,
`plan_wall_data`, `plan_beam_analysis`.
QCAD Pro 3.x: `qcad_status`, `plan_script`, `plan_render`, `plan_exec`,
`plan_dimension`, `plan_measure`, `plan_text`, `plan_hatch`,
`plan_block_insert`, `plan_array`.
Libraries: `plan_blocks`, `plan_blocks_download`, `plan_scripts_search`,
`plan_scripts_download`.
Agentic: `plan_generate`, `plan_agentic`, `plan_transpile`, `cad_sampling`.
Meta: `qcad_help`, `qcad_shutdown`, `show_qcad_status_card`,
`show_depot_card`, `show_beam_analysis_card`, `show_building_meta_card`.
Resources: `cad://depot`, `cad://depot/{filename}`. Prompts: 3 registered
in agentic_tools (`@mcp.prompt()`).

Always call `qcad_status` first when a workflow needs QCAD Pro — every Pro
tool degrades or fails without it.

## Workflow 1 — floor plan to 3D print

1. `plan_depot` → pick the DXF (or `plan_create` from primitives).
2. `plan_info(file_name)` → confirm wall layers exist.
3. `plan_to_svg(file_name)` → visual sanity check of walls/openings.
4. `plan_analyse(file_name)` → rooms, areas, doors/windows.
5. `plan_extrude(file_name, wall_height=3.0, wall_thickness=0.3)` → STL.
6. Ship the STL to freecad-mcp (`POST /api/v1/freecad/solid`) for solid work.

## Workflow 2 — annotate an existing drawing (QCAD Pro)

1. `qcad_status()` → installed + running must both be true.
2. `plan_dimension` / `plan_text` / `plan_hatch` with explicit coordinates.
3. `plan_render(file_name, format="pdf")` → high-fidelity proof.
4. Never invent coordinates — read them from `plan_measure` or `plan_info`
   bounding boxes first.

## Config

- Backend 11966, frontend 11967. Env: `QCAD_MCP_DEPOT`, `QCAD_MCP_OUTPUT`,
  `QCAD_PRO_PATH`, `MCP_BRIDGE_URLS`, `FREECAD_MCP_URL`.
- Dual transport: `--mode stdio` (Claude Desktop), `--mode http` (webapp),
  `--mode dual`. Under `QCAD_TAURI=1` stdio is forced to http.

## Troubleshooting

- QCAD Pro tools fail → `qcad_status`; check `QCAD_PRO_PATH`, start QCAD GUI.
- Empty STL → wall-layer auto-detect missed: pass `wall_layers` explicitly
  (names containing wall/mauer/wand/mur/parete/pared).
- DWG input without QCAD Pro → convert impossible; ezdxf reads DXF only.
- Live multi-document bridge (issue #1) is macOS-only proposal, deferred —
  see docs/live-bridge-proposal.md.
