# Status — qcad-mcp

**Status**: v0.3.0 — 28+ tools, zero lint errors, 39 tests, SOTA annotations.

**Repo**: `D:\Dev\repos\qcad-mcp`
**Ports**: Backend 11966, Frontend 11967

## MCP Tools (26)

### Core (7)
| Tool | Annotation | Description |
|------|-----------|-------------|
| `plan_info` | READ_ONLY | DXF metadata: layers, entity counts, bounding box, blocks |
| `plan_to_svg` | MUTATING | DXF → SVG preview with layer filtering (matplotlib) |
| `plan_extrude` | MUTATING | DXF walls → 3D STL mesh (height/thickness configurable) |
| `plan_export` | MUTATING | DXF → SVG/PNG/PDF (QCAD Pro preferred, ezdxf fallback) |
| `plan_analyse` | READ_ONLY | Room detection, area calculation, door/window identification |
| `plan_create` | MUTATING | Create DXF from primitives (line, rect, circle, text, polyline) |
| `plan_depot` | READ_ONLY | List files in persistent CAD depot with metadata |

### Modify (2)
| Tool | Annotation | Description |
|------|-----------|-------------|
| `plan_convert` | MUTATING | DWG↔DXF conversion via QCAD Pro |
| `plan_modify` | MUTATING | Delete/offset layers, rename/freeze/lock/merge layers |

### QCAD Pro (4)
| Tool | Annotation | Description |
|------|-----------|-------------|
| `qcad_status` | READ_ONLY | QCAD Pro installation, version, running state |
| `plan_script` | MUTATING | Execute arbitrary ECMAScript against a DXF document |
| `plan_render` | MUTATING | High-fidelity SVG/PDF/BMP via QCAD Pro rendering engine |
| `plan_exec` | MUTATING | Quick ECMAScript execution, no file I/O |

### Annotation (8)
| Tool | Annotation | Description |
|------|-----------|-------------|
| `plan_dimension` | MUTATING | Add aligned/radial/diametric/angular/rotated dimensions |
| `plan_measure` | READ_ONLY | Per-entity distance/angle/area measurement |
| `plan_text` | MUTATING | Text annotations with height/alignment/rotation/styling |
| `plan_hatch` | MUTATING | Hatch/fill patterns (ANSI, SOLID, AR-CONC, EARTH, etc.) |
| `plan_block_insert` | MUTATING | Insert block references (doors, windows, furniture) |
| `plan_array` | MUTATING | Rectangular or polar array of all entities |
| `plan_wall_data` | READ_ONLY | Extract wall segment coordinates as BIM-ready JSON |
| `plan_beam_analysis` | READ_ONLY | 2D beam structural analysis (direct stiffness FEM) |

### Agentic (3)
| Tool | Annotation | Description |
|------|-----------|-------------|
| `plan_agentic` | MUTATING | Natural language CAD goal → ECMAScript → execution |
| `plan_transpile` | MUTATING | AutoLISP to QCAD ECMAScript transpilation + execution |
| `cad_sampling` | READ_ONLY | Host LLM reasoning for CAD problems (MCP sampling) |

### Scripts (2)
| Tool | Annotation | Description |
|------|-----------|-------------|
| `plan_scripts_search` | READ_ONLY | Search QCAD ECMAScript libraries |
| `plan_scripts_download` | MUTATING | Download ECMAScript to local depot |

## Prompts (3)
- `cad_expert(topic)` — CAD expertise + tool guidance
- `cad_analyse_plan(file_name)` — Floor plan analysis workflow
- `cad_extrude_3d(file_name, height, thickness)` — 3D extrusion workflow

## Resources (2)
- `cad://depot` — List all depot files
- `cad://depot/{filename}` — Metadata for a specific depot file

## Quality

| Metric | Value |
|--------|-------|
| Lint (Ruff) | 0 errors |
| Lint (Biome) | 0 errors |
| TypeScript (tsc) | 0 errors |
| Tests | 39 passing |
| Webapp pages | 17 routes |
| REST endpoints | 26+ |
| Tauri native wrapper | Built and CUA-NSIS certified |
| MCPB bundle | Builds (v0.3.0 distributed) |

## Fleet Standards

| Standard | Status |
|----------|--------|
| `llms.txt` | Done |
| `llms-full.txt` | Done |
| `glama.json` | Done |
| `@mcp.tool(annotations=...)` | All 26 tools annotated |
| `Annotated[..., Field(description=...)]` | All tools SOTA compliant |
| `ctx: Context = None` type hints | All tools correct |
| `prefab-ui` dependency | Not yet added |
| `justfile` recipes | 20+ fleet-standard recipes |
| CUA-NSIS smoke test | Config and script present |

## Cross-Repo Pipeline

```
qcad-mcp (port 11966)          freecad-mcp (port 10944)
         │                              │
plan_extrude → walls.stl ──────→ mesh_to_solid → FCStd
         │                              │
plan_wall_data → wall segments ─→ bim_create_wall per segment
                                    bim_create_slab
                                    bim_create_window
                                    bim_create_door
                                    bim_export_ifc → building.ifc
```

## Short Term
- [ ] Add `prefab-ui` dependency for Prefab cards (status, depot list)
- [ ] Add `/api/v1/case-files` endpoint (for STL/VTK serving)
- [ ] Auto-download FluidX3D runner on `qcad_status` if missing
- [ ] Playwright e2e tests for webapp pages
- [ ] Integrate plan_extrude → freecad-mcp STL auto-wire (like freecad-mcp → FluidX3D)

## Medium Term
- [ ] Web-based DXF viewer (instead of SVG render)
- [ ] AI-assisted dimensioning: detect walls automatically, add dimensions
- [ ] Multi-page DXF support (architectural sets with multiple floor levels)
- [ ] IFC export from wall data (via freecad-mcp bridge)

