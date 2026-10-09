# Development — qcad-mcp

## Prereqs

Python 3.12+, `uv` (`C:\Users\sandr\.local\bin\uv.exe`), Node 22+
(`npm --prefix webapp ci`), QCAD Pro 3.x optional.

## Loop

```powershell
just bootstrap   # uv sync --all-extras + npm install + pre-commit hook
just serve       # backend dual mode on :11966
start.ps1        # backend + frontend + browser (fleet engine)
just lint        # ruff check + biome + tsc
just test        # pytest (78 tests, ~22 s)
```

`just lint` runs `ruff check src/`, `biome ci` in webapp, `tsc --noEmit`.
`just fix` applies ruff/biome autofixes. `just e2e` runs Playwright specs
(webapp/e2e) against a live backend (`just serve` first).

## Layout

- `src/qcad_mcp/server.py` — FastAPI app + FastMCP registration, REST routes,
  lifespan, CORS, entry `main()` (stdio/http/dual).
- `src/qcad_mcp/tools/` — 9 modules, each with `register(mcp)` firing
  `mcp.tool(annotations=...)` calls (40 tools).
- `src/qcad_mcp/services/` — ezdxf engine, QCAD Pro bridge, block/script
  libraries, apps/fleet routes, plan LLM.
- `src/qcad_mcp/utils/` — `response.py` (dialogic returns + auto-logging),
  `gh_cli.py` (prompt-free gh subprocess wrapper).
- `webapp/src/` — React 19 + Vite + Tailwind + Zustand; 18 routes in App.tsx.
- `native/` — Tauri 2 shell (nsis target,_BACKEND_PORT 11966).
- `run_server.py` — PyInstaller/Tauri entry (Gate J isatty shim).

## Conventions

- Tool functions: `Annotated[...] + Field(...)` params, `## Return Format` +
  `## Examples` docstrings, verb-led snake_case names, READ_ONLY/MUTATING
  annotations. Returns go through `utils/response.py`.
- No `print()` in server code (ruff T20 enforced); `logger.exception` in
  except blocks; never `return False` from import helpers — raise.
- Frontend: same-origin `/api` via vite proxy in dev; absolute backend URL
  only behind a Tauri gate (`webapp/src/lib/api.ts`).
