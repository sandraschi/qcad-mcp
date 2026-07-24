# QCAD MCP

<p align="center">
  <a href="https://github.com/casey/just"><img src="https://img.shields.io/badge/just-ready_to_go-7c5cfc?style=flat-square&logo=just&logoColor=white" alt="Just"></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff"></a>
  <a href="https://python.org"><img src="https://img.shields.io/badge/Python-3.13+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python"></a>
  <a href="https://biomejs.dev"><img src="https://img.shields.io/badge/Linted_with-Biome-60a5fa?style=flat-square&logo=biome&logoColor=white" alt="Biome"></a>
  <a href="https://github.com/PrefectHQ/fastmcp"><img src="https://img.shields.io/badge/FastMCP-3.2-7c5cfc?style=flat-square" alt="FastMCP"></a>
</p>

**AI-driven 2D CAD automation — DXF/DWG parsing, 3D extrusion, persistent file depot, room analysis, and full CRUD management.** 7 MCP tools for DXF processing. Your AI assistant becomes a QCAD Pro operator.

| | |
|--:|--|
| **You might use this if…** | You want your AI to process floor plans programmatically, convert DXF to 3D for Resonite/Unity3D, maintain a persistent CAD file depot, or automate drafting workflows. |
| **What it connects to** | `ezdxf` (free Python engine) for all parsing + rendering + extrusion + analysis |
| **Ports** | Backend **10966**, Dashboard **10967** |
| **Start** | `just bootstrap` then `start.ps1` |

## MCP Tools

| Tool | Access | Purpose |
|------|--------|---------|
| `plan_depot` | READ | List files in the persistent CAD depot with metadata |
| `plan_info` | READ | DXF metadata: layers, entity counts, bounding box, blocks |
| `plan_create` | MUTATE | Create DXF from primitives (line, rect, circle, text, polyline) |
| `plan_to_svg` | MUTATE | DXF → SVG preview with layer filtering |
| `plan_extrude` | MUTATE | DXF walls → 3D STL mesh (configurable height/thickness) |
| `plan_export` | MUTATE | DXF → SVG/PNG/PDF (ezdxf or QCAD Pro) |
| `plan_analyse` | READ | Room detection, area calculation, door/window identification |
| `plan_measure` | READ | Measure distances and lengths in a DXF |
| `plan_wall_data` | READ | Extract wall segments as BIM-ready JSON (QCAD Pro) |
| `plan_beam_analysis` | READ | 2D beam FEM analysis (numpy, no QCAD needed) |
| `plan_dimension` | MUTATE | Add aligned/linear/angular/radial dimensions (QCAD Pro) |
| `plan_text` | MUTATE | Add text annotations (QCAD Pro) |
| `plan_hatch` | MUTATE | Add hatch patterns (QCAD Pro) |
| `plan_block_insert` | MUTATE | Insert CAD blocks from library (QCAD Pro) |
| `plan_array` | MUTATE | Rectangular/polar array patterns (QCAD Pro) |
| `plan_convert` | MUTATE | Convert between DXF and DWG (QCAD Pro) |
| `plan_modify` | MUTATE | Delete/offset/rename/freeze layers |
| `plan_script` | MUTATE | Execute arbitrary ECMAScript in QCAD Pro |
| `plan_render` | MUTATE | High-fidelity SVG/PDF/BMP render via QCAD Pro |
| `plan_exec` | MUTATE | Quick ECMAScript snippet execution |
| `plan_blocks` | READ | Search 4800+ CAD blocks from part library |
| `plan_blocks_download` | MUTATE | Download a block DXF from library |
| `plan_scripts_search` | READ | Search QCAD ECMAScript scripts gallery |
| `plan_scripts_download` | MUTATE | Download a script from gallery/Gist |
| `qcad_status` | READ | QCAD Pro install/running/version report |
| `plan_agentic` | MUTATE | NL → ECMAScript via AI sampling (MCP only, needs QCAD Pro) |
| `plan_transpile` | MUTATE | AutoLISP → QCAD ECMAScript translation (MCP only, needs QCAD Pro) |

## CAD Depot (Persistent File Storage)

All CAD files are stored in a persistent depot at `%LOCALAPPDATA%\qcad-mcp\depot` — survives server restarts and system reboots. Configurable via `QCAD_MCP_DEPOT` env var.

**Depot CRUD via REST API:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/depot` | GET | List all files with metadata (size, dates, description, tags) |
| `/api/v1/depot/{name}` | GET | Download a DXF file |
| `/api/v1/depot/{name}` | PUT | Rename or update description/tags |
| `/api/v1/depot/{name}` | DELETE | Remove file + metadata sidecar |
| `/api/v1/depot/create` | POST | Create DXF from JSON entity spec (line, rect, circle, text, polyline) |
| `/api/v1/depot/upload` | POST | Upload DXF/DWG directly to depot |

## REST API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/status` | GET | Server health, ezdxf version, QCAD Pro status |
| `/api/v1/upload` | POST | Upload DXF/DWG (also saved to depot) |
| `/api/v1/download/{name}` | GET | Download SVG/STL/PDF/PNG outputs |
| `/api/v1/files` | GET | List all files (depot + outputs) |
| `/api/v1/depot/*` | GET/PUT/DELETE | Full CRUD on the persistent CAD depot |
| `/api/v1/control/tool` | POST | Execute any MCP tool |
| `/api/v1/logs/stream` | GET | SSE live log stream |
| `/api/v1/chat` | POST | Chat with CAD expert via Ollama |
| `/api/v1/settings` | GET/PUT | LLM + extrusion defaults + QCAD Pro path |

## Webapp Pages

| Route | Page | Description |
|-------|------|-------------|
| `/` | Dashboard | Hero banner, QCAD Pro status panel, depot stats, ezdxf version |
| `/demo` | AI CAD Demo | NL → floor plan → SVG → 3D STL. Baroque church, mob compound, art museum presets |
| `/depot` | Depot | Full CRUD file browser with SVG preview, create DXF wizard, upload, rename, delete |
| `/viewer` | Viewer | DXF upload + SVG preview with per-layer toggle |
| `/extrude` | Extrude | DXF → STL with wall height/thickness/wall-layer controls |
| `/analyse` | Analyse | Room detection, area table, door/window list |
| `/layers` | Layers | Layer visibility, freeze/lock, rename, bulk operations |
| `/blocks` | Blocks | Search 4800+ CAD blocks from library with download |
| `/scripts` | Scripts | Browse QCAD ECMAScript scripts gallery + save local scripts |
| `/agentic` | AI Agent | Autonomous multi-step CAD workflow (QCAD Pro) |
| `/batch` | Batch | Run info/analysis/extrude across all depot files. STL batch extrude with gallery |
| `/pipeline` | Pipeline | 5-step wizard: describe → SVG → analyse → STL → FreeCAD wall data export |
| `/playground` | Playground | Tool API tester: select any tool, edit JSON args, execute, view raw response |
| `/models` | Models | Uploads vs outputs listing with download |
| `/logs` | Logs | Live SSE log viewer with filter/export/pause |
| `/settings` | Settings | LLM provider/model, extrusion defaults, QCAD Pro path |
| `/help` | Help | 10-tabbed reference: QCAD, ezdxf, tools, pipeline, formats, fleet |
| `docs/floorplan-sources.md` | — | Free, paid, and historic floorplan sources + raster→DXF pipeline |

## Quick Start

```powershell
just bootstrap   # uv sync + npm install
start.ps1        # kills zombies, starts backend + frontend, opens browser
```

## MCP Client Config

```json
{
  "mcpServers": {
    "qcad": {
      "url": "http://localhost:10966/sse",
      "transport": "sse"
    }
  }
}
```

## Raster → DXF Pipeline (Planned)

Scanning a floorplan print into a working DXF is straightforward:

```
Book/magazine page → scanner (300-600 DPI)          inkscape-mcp
                         ↓                          (Trace Bitmap)
                    Potrace / Inkscape                    ↓
                         ↓                          QCAD MCP
                    Raw vector DXF                    (plan_modify)
                         ↓
                    Clean up in QCAD / plan_modify
```

| Step | Tool | What it does |
|------|------|-------------|
| Scan | Any scanner | 300-600 DPI, grayscale or B&W, save as PNG/TIFF |
| Vectorize | **inkscape-mcp** `trace_bitmap()` or potrace CLI | Converts raster lines to SVG paths |
| Convert | SVG → DXF (via potrace or ezdxf) | Opens in any CAD program |
| Clean | **qcad-mcp** `plan_modify` | Merge short segments, delete stray marks, re-layer, re-dimension |

Two approaches:
1. **inkscape-mcp** route — send the scanned PNG to inkscape-mcp's `trace_bitmap()` tool, get back SVG with proper path geometry. The SVG imports cleanly into QCAD as workable entities.
2. **potrace in qcad-mcp** — add a `plan_raster_to_dxf(file_name)` tool that wraps potrace + ezdxf. Self-contained, no external server needed.

Either way, the result goes through `plan_modify` for cleanup (delete noise, merge wall segments, re-assign layers, re-add dimensions). The baroque church preset in the Demo page proves the parametric geometry works — scanning would let you capture *actual* existing buildings.

## QCAD Pro Pricing — €50? Really?

QCAD Professional sells for **€50.40** for a single-user license — lifetime, no subscription. That looks absurd next to AutoCAD at $2,000+/year, but RibbonSoft's revenue model is more nuanced:

| Product | Price | Market |
|---------|-------|--------|
| **Community Edition** | **Free** (GPLv3) | Hobbyists, students, tinkerers |
| **QCAD Professional** | €50.40 | Individual professionals, small firms |
| **QCAD Pro Site License** | €440.40 | Companies (unlimited seats, single site) |
| **QCAD Pro Server License** | €583.20 | Self-hosted deployment |
| **QCAD Pro Scalable Server** | €1,771.20 | Enterprise-scale |
| **QCAD/CAM** (CNC add-on) | €132.00 | Manufacturing |
| **QCAD/CAM Site License** | €1,173.60 | CNC shops |
| **Books / E-Books** | €40–42 each | Documentation, passive income |

The strategy is open-core freemium with **enterprise site-license extraction**:

1. **Community Edition** is genuinely free and capable (GPLv3). It's a giant funnel — architects, makers, and students learn on it, recommend it, and eventually their employer buys a site license.
2. **€50 individual** is friction-free "impulse buy" pricing — no PO approval needed, no vendor negotiation. You just buy it.
3. **Site & server licenses (€440–€1,771)** are where the real revenue lives. An architecture firm with 20 seats paying €440 beats 200 individuals paying €50. And server licenses for SaaS/on-prem deployment scale further.
4. **QCAD/CAM at €132** captures the CNC/manufacturing niche — a separate, higher-value market.
5. **Books at €40** are pure margin — the manual is already written, printing costs are negligible.

RibbonSoft is a Swiss **GmbH** (limited company) based in Sarnen, not retirees. 100% of their office energy is from Swiss hydropower (they're proud enough to put it in the footer). They've been doing this since 1999 — 26+ years of sustainable bootstrapping.

**Who pays?** Ganesh in Bangalore runs the Community Edition for his residential projects — it handles DXF perfectly for Indian building code drawings. When a client demands DWG or PDF export, he drops €50 on Pro — one job pays for it. As his practice scales past 5 seats, he graduates to a site license. Meanwhile a European architecture firm pays €440 for compliance reasons and never thinks twice. The Bay Area Autodesk tax ($2,500+/year) only makes sense when someone else is paying.

€50 clears every threshold, everywhere. No PO approval, no vendor negotiation, no subscription clock. You buy it once and own it.

## Quality Stack

- **Python**: [Ruff](https://astral.sh/ruff) linter — zero errors across 5 MCP tools + depot CRUD
- **Frontend**: [Biome](https://biomejs.dev/) + `tsc` — zero errors across 9 TypeScript pages
- **Protocol**: FastMCP 3.2 SSE transport + 10 REST endpoints
- **Automation**: [Justfile](./justfile) recipes for all fleet operations
- **AI Protocol**: FastMCP 3.2 with SSE transport

## License

MIT — see [LICENSE](LICENSE).
