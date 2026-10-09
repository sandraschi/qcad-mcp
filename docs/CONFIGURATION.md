# Configuration — qcad-mcp

All knobs in one place. Copy `.env.example` to `.env` and adjust.

## Ports

| Service | Port | Source |
|---|---|---|
| Backend (FastAPI + MCP `/mcp`) | 11966 | `fleet-start.config.ps1` BackendPort, `--port` default in `server.py` |
| Frontend (Vite) | 11967 | `fleet-start.config.ps1` FrontendPort, `webapp/vite.config.ts` |

Registry: `mcp-central-docs/operations/WEBAPP_PORTS.md` (11966/11967).

## Environment variables

| Var | Default | Purpose |
|---|---|---|
| `MCP_TRANSPORT` | stdio | `stdio` (Claude Desktop) or `http` (Tauri/browser) |
| `MCP_HOST` / `MCP_PORT` | 127.0.0.1 / 11966 | HTTP bind; `run_server.py` also honours `PORT` |
| `WEB_PORT` | 11966 | Set by launcher for the backend process |
| `QCAD_MCP_DEPOT` | `%LOCALAPPDATA%\qcad-mcp\depot` | Persistent CAD file store |
| `QCAD_MCP_OUTPUT` | `%LOCALAPPDATA%\qcad-mcp\output` | SVG/STL/PDF/PNG outputs |
| `QCAD_PRO_PATH` | auto-detect `C:\Program Files\QCAD` | QCAD Pro install for DWG/render/script tools |
| `MCP_BRIDGE_URLS` | empty | Comma-separated MCP servers to proxy (federation) |
| `FREECAD_MCP_URL` | http://127.0.0.1:10944 | freecad-mcp handoff for STL→solid |
| `QCAD_TAURI` / `QCAD_MCP_TAURI` | unset | `=1` forces HTTP mode, skips QCAD GUI auto-launch |

## Transports

- `uv run python -m qcad_mcp.server --mode stdio` — MCP clients.
- `uv run python -m qcad_mcp.server --mode http --port 11966` — webapp/Tauri.
- `uv run python -m qcad_mcp.server --mode dual` — both.
- Stdio `main()` probes `/mcp` before DB init and uses `create_proxy()` when
  a live HTTP daemon answers (no double-daemon).

## QCAD Pro (optional wrappee)

Free tier (ezdxf) covers parsing, SVG preview, extrusion, analysis, depot
CRUD. QCAD Pro 3.x adds DWG convert, native render, dimensions, hatches,
text, arrays, block insert, and full ECMAScript (`plan_script`/`plan_exec`,
120 s timeout). `qcad_status` reports install/running/version.
