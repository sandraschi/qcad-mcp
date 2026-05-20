# QCAD MCP

<p align="center">
  <a href="https://github.com/casey/just"><img src="https://img.shields.io/badge/just-ready_to_go-7c5cfc?style=flat-square&logo=just&logoColor=white" alt="Just"></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff"></a>
  <a href="https://python.org"><img src="https://img.shields.io/badge/Python-3.13+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python"></a>
  <a href="https://biomejs.dev"><img src="https://img.shields.io/badge/Linted_with-Biome-60a5fa?style=flat-square&logo=biome&logoColor=white" alt="Biome"></a>
  <a href="https://github.com/PrefectHQ/fastmcp"><img src="https://img.shields.io/badge/FastMCP-3.2-7c5cfc?style=flat-square" alt="FastMCP"></a>
</p>

[![CI](https://github.com/sandraschi/qcad-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/sandraschi/qcad-mcp/actions)
**AI-driven 2D CAD automation — DXF/DWG parsing, 3D extrusion, ECMAScript scripting, native rendering, dimensions, annotations, and agentic workflows.** 22 MCP tools. Your AI assistant becomes a QCAD Pro operator.

| | |
|--:|--|
| **You might use this if…** | You want your AI to write and execute QCAD scripts, process floor plans programmatically, convert DXF to 3D for Resonite/Unity3D, or automate CAD drafting without opening QCAD. |
| **What it connects to** | `ezdxf` (free Python engine) for parsing/extrusion + **QCAD Pro** (~€42) for ECMAScript bridge, native rendering, DWG |
| **Ports** | Backend **10966**, Dashboard **10967** |
| **Start** | `just bootstrap` then `start.ps1` |

## Two-Tier Engine

| Tier | Cost | Powers |
|------|------|--------|
| **ezdxf** | Free | DXF parsing, SVG preview, STL extrusion, room analysis, DXF creation from primitives, entity/layer modification, block search |
| **QCAD Pro** | ~€42 | **ECMAScript bridge** (AI writes QCAD scripts), **native SVG/PDF/BMP** (perfect hatches/fonts/dims), **dimensions**, **measurements**, **text annotations**, **hatch patterns**, **agentic workflows**, **DWG import/export** |

## QCAD Pro Features

With QCAD Pro 3.x installed the AI agent gains full CAD automation:

- **`plan_script`** — Execute arbitrary ECMAScript against DXF documents. Full QCAD API: entities, layers, blocks, operations. The AI writes code, QCAD Pro runs it headless. **No script library needed — the LLM is the library.**
- **`plan_agentic`** — Natural language CAD goals → ECMAScript → executed. "Create a 10m×8m floor plan with 4 rooms and dimensions" → done. Unlike hunting for a 20-year-old AutoLISP routine on a forum.
- **`plan_render`** — Native SVG/PDF/BMP output with correct hatches, TrueType fonts, lineweights, dimension styles.
- **`plan_dimension`** — Add aligned, radial, diametric, angular dimensions to drawings.
- **`plan_measure`** — Per-entity distance, angle, area, perimeter measurement via QCAD's geometry engine.
- **`plan_text`** / **`plan_hatch`** — Text annotations with full styling + hatch/fill patterns (ANSI31-38, AR-CONC, SOLID).
- **`plan_convert`** — DWG↔DXF conversion via Teigha engine.

## Documentation Index

| Guide | Content |
| :--- | :--- |
| **[Installation](docs/install.md)** | Prerequisites, ezdxf, QCAD Pro setup, bootstrap |
| **[Architecture](ARCHITECTURE.md)** | Two-tier engine, 20-tool table, service layer, pipeline |
| **[FreeCAD Pipeline](docs/freecad-pipeline.md)** | NL→DXF→STL→BIM→IFC cross-repo chain with freecad-mcp |
| **[MCP Tools](docs/mcp-tools.md)** | All 22 tools with examples, return formats |
| **[AI Tooling](docs/ai-tooling.md)** | Ollama CAD chat, agentic plan analysis workflows |
| **[About QCAD](docs/about-qcad.md)** | History, scripting API, ezdxf vs QCAD Pro, AutoCAD comparison |
| **[QCAD Pro vs. AutoCAD LT](docs/qcad-pro-vs-autocad-lt.md)** | Feature comparison, scripting, pricing, platform support |
| **[Webapp README](webapp/README.md)** | 12-page React dashboard: depot, viewer, extrude, blocks, layers |

## Quick Start

```powershell
# 1. Bootstrap
just bootstrap   # uv sync + npm install

# 2. (Optional) Set QCAD Pro path if installed
$env:QCAD_PRO_PATH = "C:\Program Files\QCAD"

# 3. Launch
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

Once connected, call `qcad_status` to verify QCAD Pro availability, then `plan_info` on uploaded files, or `plan_script` to execute CAD operations.

## Industrial Quality Stack

- **Python (Core)**: [Ruff](https://astral.sh/ruff) for linting. 22 MCP tools on FastMCP 3.2. Zero lint errors.
- **Webapp (UI)**: [Biome](https://biomejs.dev/) + `tsc` for formatting and type safety. Zero errors across 18 files.
- **Protocol**: FastMCP 3.2 SSE transport + REST API (20+ endpoints).
- **Automation**: [Justfile](./justfile) recipes for all fleet operations.

## License

MIT — see [LICENSE](LICENSE).
