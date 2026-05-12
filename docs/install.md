# Installation

## Prerequisites

| Tool | Required | Notes |
|:---|:---|:---|
| **Python 3.12+** | Yes | `uv` package manager |
| **uv** | Yes | Fleet package manager |
| **ezdxf** | Yes | Pure Python DXF parser (MIT), installed via uv |
| **QCAD Pro CLI** | Optional | For DWG support and high-fidelity PDF export (~€50.40) |
| **Node.js 20+** | Yes | For the Vite dashboard |

## ezdxf

The core engine is `ezdxf`, a pure-Python library (no binary dependencies). It reads DXF R12 through R2023, handles layers, blocks, linetypes, and most entity types. Installed automatically by `uv sync`.

## QCAD Pro Setup (Optional)

QCAD Pro adds:
- DWG file reading/writing
- High-fidelity PDF export (`dwg2pdf`, `dwg2svg` CLI tools)
- Better font rendering

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
