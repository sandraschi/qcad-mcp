# qcad-mcp — 2D CAD MCP Server (DXF/DWG → SVG/STL + ECMAScript bridge)

**Vision**: Upload a floor plan DXF, preview it in the browser, extrude walls to 3D, annotate and dimension, import into Resonite/Unity3D. All through MCP tools. With QCAD Pro, the AI agent writes ECMAScript to automate any CAD operation — no pre-existing script library required, the LLM generates code on-demand.

**Price of entry**: €0 (Community Edition + `ezdxf`) or ~€42 (QCAD Pro for DWG + ECMAScript bridge + native rendering).

---

## Architecture

```
DXF/DWG file
    │
    ├── ezdxf (pure Python, free) ──→ JSON entity list, layers, blocks
    │   ├── → SVG preview (webapp)
    │   └── → STL extrusion (walls → 3D)
    │
    └── QCAD Pro (€42, Swiss-made) ──→ ECMAScript bridge + native rendering
        ├── → plan_script / plan_exec (arbitrary ECMAScript execution)
        ├── → plan_render (high-fidelity SVG/PDF/BMP)
        ├── → plan_dimension (aligned/radial/angular dimensions)
        ├── → plan_measure (per-entity distance/angle/area)
        ├── → plan_text / plan_hatch (annotations + fill patterns)
        ├── → plan_agentic (NL goal → ECMAScript → executed)
        └── → plan_convert (DWG↔DXF)
```

### Two-Tier Engine Design

**Tier 1 — ezdxf** (always available, zero cost):
- All parsing: layers, entities, blocks, bounding boxes
- SVG preview via matplotlib backend
- STL extrusion (wall polyline → 3D mesh)
- Room analysis (closed polyline detection)
- DXF creation from primitives

**Tier 2 — QCAD Pro** (optional, ~€42 one-time):
- ECMAScript bridge: execute arbitrary scripts against DXF documents
- Native rendering: perfect hatches, TrueType fonts, lineweights, dimensions
- Geometry engine: precise measurements, entity type detection
- Dimension, text, hatch entity creation
- DWG import/export via Teigha

---

## MCP Tools (20 total)

### ezdxf Tier (always available)
| Tool | Access | Purpose |
|------|--------|---------|
| `plan_info` | READ_ONLY | Layers, entity counts, bounding box, blocks |
| `plan_to_svg` | MUTATING | DXF → SVG preview with layer filtering |
| `plan_extrude` | MUTATING | DXF walls → 3D STL mesh |
| `plan_export` | MUTATING | DXF → SVG/PNG/PDF (QCAD Pro preferred) |
| `plan_analyse` | READ_ONLY | Room detection, area, door/window ID |
| `plan_create` | MUTATING | Create DXF from geometric primitives |
| `plan_depot` | READ_ONLY | List files in the depot |
| `plan_modify` | MUTATING | Delete, offset, layer operations |
| `plan_blocks` | READ_ONLY | Search CAD block libraries |
| `plan_blocks_download` | MUTATING | Download blocks to depot |

### QCAD Pro Tier (requires QCAD Pro 3.x)
| Tool | Access | Purpose |
|------|--------|---------|
| `qcad_status` | READ_ONLY | Pro install/version/running detection |
| `plan_script` | MUTATING | Execute arbitrary ECMAScript against DXF |
| `plan_render` | MUTATING | Native SVG/PDF/BMP rendering |
| `plan_exec` | MUTATING | Quick ECMAScript execution, no file I/O |
| `plan_convert` | MUTATING | DWG↔DXF conversion |
| `plan_dimension` | MUTATING | Add aligned/radial/angular dimensions |
| `plan_agentic` | MUTATING | NL goal → ECMAScript → executed |
| `plan_measure` | READ_ONLY | Per-entity distance/angle/area measurement |
| `plan_text` | MUTATING | Text annotations with styling |
| `plan_hatch` | MUTATING | Hatch/fill patterns (ANSI, SOLID, AR-CONC) |

---

## Service Layer

`src/qcad_mcp/services/qcad_pro.py` — Detection, CLI execution, ECMAScript bridge, rendering.

Key functions:
- `is_installed()` / `is_running()` / `get_version()` — QCAD Pro status
- `run_script(code, input_file, output_file)` — ECMAScript bridge (headless)
- `exec_in_live(code, file_name)` — Quick script execution
- `render(input, output, format)` — Native SVG/PDF/BMP rendering
- `convert(input, output, format)` — DWG↔DXF conversion

The bridge wraps user ECMAScript in a template that imports the input file, runs code, gathers entity/layer metadata, and exports output. Structured results are extracted from stdout via `__QCAD_MCP_RESULT__` JSON markers.

---

## Webapp

Fleet-standard Vite + React layout on port 10967:

| Page | Purpose |
|------|---------|
| **Dashboard** | File counts, QCAD Pro status, quick actions |
| **Depot** | Full CRUD with SVG preview, DXF creation wizard, upload |
| **Viewer** | DXF upload + SVG preview with per-layer toggle |
| **Extrude** | DXF → STL with wall height/thickness controls |
| **Analyse** | Room detection, area table, door/window list |
| **Blocks** | Search + download CAD blocks from 3 sources |
| **Layers** | Layer manager (color, freeze, lock, delete) |
| **Batch** | Run plan_info/plan_analyse on all depot files |
| **Models** | Uploads vs outputs listing with download |
| **Logs** | Live SSE log viewer with filter/export/pause |
| **Settings** | Ollama URL/model, extrusion defaults, QCAD Pro path |
| **Help** | 9-tabbed reference covering QCAD, ezdxf, scripting, tools |

---

## Resonite Pipeline

```
qcad-mcp plan_extrude → STL
    │
    ├── freecad-mcp step_to_stl (optimise, decimate)
    │       │
    │       └── Resonite (import STL as static mesh)
    │
    └── Direct: Resonite supports STL import natively
```

---

## Fleet Registration

| Item | Value |
|------|-------|
| **Repo** | `D:\Dev\repos\qcad-mcp` |
| **Ports** | Backend 10966, Frontend 10967 |
| **Version** | 0.3.0 |
| **Python engine** | `ezdxf` (MIT, free) |
| **Pro engine** | QCAD Pro 3.x (~€42, for ECMAScript bridge + DWG) |
| **Linting** | Ruff (Python), Biome (TSX), tsc (TypeScript) |
