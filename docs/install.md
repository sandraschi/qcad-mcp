# Installation

## Prerequisites

| Tool | Required | Notes |
|:---|:---|:---|
| **Python 3.12+** | Yes | `uv` package manager |
| **uv** | Yes | Fleet package manager |
| **ezdxf** | Yes | Pure Python DXF parser (MIT), installed via uv |
| **QCAD Pro** | Recommended | ~€42 — enables ECMAScript bridge, native rendering, DWG support, dimensions, annotations. 10 of 20 tools require it. |
| **Node.js 20+** | Yes | For the Vite dashboard |

## ezdxf

The core engine is `ezdxf`, a pure-Python library (no binary dependencies). It reads DXF R12 through R2023, handles layers, blocks, linetypes, and most entity types. Installed automatically by `uv sync`.

## QCAD Pro Setup (Recommended)

QCAD Pro adds the ECMAScript bridge and all annotation/measurement/dimension tools. **10 of the 20 MCP tools require it.** Without QCAD Pro, the ezdxf tier still works for parsing, SVG preview, STL extrusion, and room analysis.

With QCAD Pro, the AI agent can:
- **Write and execute CAD scripts** via `plan_script` / `plan_exec` (ECMAScript, LLM-friendly)
- **Generate CAD from natural language** via `plan_agentic`
- **Render native SVG/PDF/BMP** with correct hatches, fonts, lineweights via `plan_render`
- **Add dimensions, text, hatches** via `plan_dimension`, `plan_text`, `plan_hatch`
- **Measure distances/angles/areas** via `plan_measure`
- **Convert DWG↔DXF** via `plan_convert`
- **Modify entities and layers** via `plan_modify` (enhanced)

**No script library needed — the LLM writes ECMAScript on-demand.** Unlike AutoCAD's 40-year AutoLISP ecosystem, QCAD Pro doesn't depend on pre-existing scripts. The AI generates code fresh for each task.

Download from [qcad.org](https://www.qcad.org/en/download). Default path:

```
C:\Program Files\QCAD\qcad.exe
```

Set `QCAD_PRO_PATH` to override:
```powershell
$env:QCAD_PRO_PATH = "C:\Program Files\QCAD\qcad.exe"
```

## Bootstrap

```powershell
just bootstrap   # uv sync && cd webapp && npm install
```

## Start

```powershell
# All-in-one (backend + frontend + browser):
start.ps1

# Or separately:
just serve       # backend on :10966
just web         # frontend on :10967

# MCP stdio mode (no webapp):
just stdio
```

## Verify

```powershell
just health       # curl http://localhost:10966/api/v1/status
```

Open `http://localhost:10967` for the dashboard.
