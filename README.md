# QCAD MCP

[![FastMCP Version](https://img.shields.io/badge/FastMCP-3.2.0-blue?style=flat-square&logo=python&logoColor=white)](https://github.com/sandraschi/fastmcp)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Linted with Biome](https://img.shields.io/badge/Linted_with-Biome-60a5fa?style=flat-square&logo=biome&logoColor=white)](https://biomejs.dev/)
[![Built with Just](https://img.shields.io/badge/Built_with-Just-000000?style=flat-square&logo=gnu-bash&logoColor=white)](https://github.com/casey/just)

**DXF/DWG floor plans to SVG + 3D STL, through your AI assistant.** — Parse 2D CAD drawings, render previews, extrude walls to 3D, detect rooms, and export to STL for game engines and 3D printing.

| | |
|--:|--|
| **You might use this if…** | You need to process floor plans programmatically, convert DXF to 3D for Resonite/Unity3D, or analyse building layouts without opening QCAD. |
| **What it connects to** | `ezdxf` (pure Python DXF parser), optional QCAD Pro CLI for high-fidelity PDF/DWG export |
| **Ports** | Backend **10966**, Dashboard **10967** |
| **Start** | `just bootstrap` then `start.ps1` |

## Documentation Index

| Guide | Content |
| :--- | :--- |
| **[Installation](docs/install.md)** | Prerequisites, ezdxf, QCAD Pro (optional), bootstrap |
| **[Architecture](docs/architecture.md)** | Data pipeline, DXF→SVG→STL, depot storage, fleet integration |
| **[MCP Tools](docs/mcp-tools.md)** | All 7 tools: plan_info, plan_to_svg, plan_extrude, plan_export, plan_analyse, plan_create, plan_depot |
| **[AI Tooling](docs/ai-tooling.md)** | Ollama CAD chat, agentic plan analysis workflows |
| **[About QCAD](docs/about-qcad.md)** | History, scripting, ezdxf vs QCAD Pro, comparison to AutoCAD |
| **[Webapp README](webapp/README.md)** | Dashboard frontend: pages, depot, extrude UI, viewer |

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

## Industrial Quality Stack

- **Python (Core)**: [Ruff](https://astral.sh/ruff) for linting and formatting.
- **Webapp (UI)**: [Biome](https://biomejs.dev/) for sub-millisecond linting.
- **Protocol**: FastMCP 3.2 SSE transport with hardened stdout/stderr isolation.
- **Automation**: [Justfile](./justfile) recipes for all fleet operations.

## License

MIT — see [LICENSE](LICENSE).
