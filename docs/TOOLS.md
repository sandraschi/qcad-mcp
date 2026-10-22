# Tools — qcad-mcp (v0.5.0: 8 portmanteaus + 4 cards)

Registered via `register(mcp)` in `src/qcad_mcp/tools/portmanteau.py` (+
`prefab_cards.py`). Each portmanteau takes an `op` Literal discriminator plus
the op's parameters; unneeded params are ignored. Full signatures in
`llms-full.txt`. `qcad(op="help")` prints this catalog live.

## Core — ezdxf, no QCAD Pro: `plan`

| Op | Purpose |
|---|---|
| `info` | DXF metadata: layers, entity counts, bbox, blocks |
| `to_svg` | DXF → SVG preview, `svg_layers` filter, background |
| `extrude` | Wall LINE/LWPOLYLINE → 3D STL (h=3.0 m, t=0.3 m defaults) |
| `stack` | Multi-storey extrusion |
| `obj` / `glb` | STL → OBJ / GLB shuttle (Resonite path) |
| `drawings` | Drawing set helpers (elevations, section, iso, roof) |
| `export` | DXF → SVG/PDF/PNG (Pro first, ezdxf fallback) |
| `analyse` | Rooms, areas, doors/windows |
| `create` | DXF from primitives (line/rect/circle/text/polyline) |
| `depot` | Depot listing with sidecar metadata |

## Edits: `plan_edit`

| Op | Purpose |
|---|---|
| `convert` | DWG↔DXF via QCAD Pro CLI |
| `modify` | Delete/offset/colour/rename/freeze/lock/merge layers |

## Annotations + BIM data: `plan_annotate`

| Op | Purpose |
|---|---|
| `dimension` | Aligned/rotated/radial/diametric/angular dimensions |
| `measure` | Per-entity distance/angle/area (read-only) |
| `text` | Text annotations with height/alignment/rotation |
| `hatch` | Hatch/fill patterns (ANSI31-38, AR-CONC, SOLID, …) |
| `block_insert` | Insert blocks from library or drawing |
| `array` | Rectangular/polar copies |
| `wall_data` | Wall segments as BIM JSON for freecad-mcp (read-only) |
| `beam_analysis` | numpy FEM: moments, shear, deflection (read-only) |

## BIM handoff: `plan_bim`

| Op | Purpose |
|---|---|
| `auto_dimension` | Auto-dimension wall geometry |
| `building_meta` | Storey/level metadata |
| `to_ifc_data` | Wall data as IFC-shaped JSON |

## QCAD Pro: `plan_pro`

| Op | Purpose |
|---|---|
| `script` | Arbitrary ECMAScript (120 s), optional DXF in/out |
| `render` | Hi-fi SVG/PDF/BMP render |
| `exec` | Quick snippet, no file I/O |

## Libraries: `plan_library`

| Op | Purpose |
|---|---|
| `blocks` | Search 4800+ CAD blocks |
| `blocks_download` | Download a block DXF to the depot |
| `scripts_search` | Search gallery/Gist/bundled ECMAScript |
| `scripts_download` | Download a script to the depot |

## AI: `plan_ai`

| Op | Purpose |
|---|---|
| `generate` | NL brief → floor-plan DXF (local LLM fallback) |
| `agentic` | NL goal → ECMAScript → executed (sampling) |
| `transpile` | AutoLISP → QCAD ECMAScript |
| `sampling` | Host-LLM reasoning about a CAD question |

## Server: `qcad`

| Op | Purpose |
|---|---|
| `status` | QCAD Pro install/running/version (read-only) |
| `help` | This catalog, live (read-only) |
| `shutdown` | Orderly exit, `confirm=true` |

## Prefab cards (read-only display)

`show_qcad_status_card`, `show_depot_card`, `show_beam_analysis_card`,
`show_building_meta_card`.

## REST equivalents (selection)

Depot CRUD `/api/v1/depot*`, `/api/v1/upload`, `/api/v1/download/{f}`,
tool bridge `/api/v1/control/tool` (tool + `op` in arguments),
chat `/api/v1/chat` + `/api/llm/chat` + `/api/llm/chat/stream`,
LLM `/api/llm/providers|models|gpus|loaded|discover|onboarding`,
skills `/api/skills`, tools `/api/tools`,
diagnostics `/api/v1/diagnostics`, health `/api/v1/health|/status`,
shutdown `POST /api/shutdown`.
