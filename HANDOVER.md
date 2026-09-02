# Handover — qcad-mcp (2026-09-01)

## State
- **Ports moved 10966/10967 → 11966/11967** (Docker Desktop's `wslrelay`/`com.docker.backend` squats the 10960-11000 range on Goliath; `10966` was `Listen` by Docker, killing `free_port` and the smoke test). All 27 files patched (backed up as `*.20250901_173500.bak`), `WEBAPP_PORTS.md` updated to `11966/11967`.
- **PyInstaller backend builds** (54 MB) after adding `opentelemetry.context.contextvars_context` + `opentelemetry.trace` to `hiddenimports` in `qcad-mcp-backend.spec` (was crashing with `opentelemetry.context` `StopIteration` on import). Build is now clean.
- **Tauri `native/`** fixed like freecad: `main.rs` spawns backend on a `std::thread` (not sync in `setup()`), `RunEvent::Exit` does `kill+wait`, `backend.rs` `resolve_bundled_backend` falls back to `resource_dir()` + `exe_dir/resources/` + `current_exe` parent; `free_port` now ONLY kills `qcad-mcp-*` (never arbitrary PID → cannot kill Docker). `cargo check` 0.
- **`src-tauri/` twin removed** (backed up to `%LOCALAPPDATA%\Temp\opencode\qcad-src-tauri.bak.20260901`); `native/` is canonical.
- **Gate J**: `run_server.py` + `src/qcad_mcp/server.py::main()` now isatty-shim + force `--mode http` when `QCAD_TAURI`/`QCAD_MCP_TAURI=1`.

## BLOCKER — CUA NSIS smoke Phase 3 fails
`scripts/cua-smoke.py --config scripts/cua-nsis-config.json`:
- Phase 1 Kill stale: PASS
- Phase 2 Install: PASS (`QCAD MCP_0.4.0_x64-setup.exe` 56 MB, installs to `%LOCALAPPDATA%\QCAD MCP\`)
- Phase 3 Launch: **FATAL Backend not reachable after 30s**

`11966` is free before smoke (verified `Get-NetTCPConnection`). The `qcad-mcp-native.exe` launches but the backend (spawned by `native/src/backend.rs::spawn_backend`) does not listen on `11966` within 30s. `freecad-mcp` on `10944` passes 11/11, so this is qcad-specific.

**Suspects (in order):**
1. **Cold start >30s** — `qcad` backend imports `matplotlib` (Agg) + `opentelemetry` + `ezdxf`; on first run after NSIS install it materializes/copies the 54 MB backend from `resources/` and cold-imports. Check `%LOCALAPPDATA%\ai.fleet.qcad-mcp\logs\backend-spawn.log` for `Backend health check ... (attempt N)` and whether it ever reaches `PASSED`.
2. **`backend-spawn.log` fallback** — verify the log actually got written (the freecad fix added `exe_dir/logs` + `LOCALAPPDATA\ai.fleet.qcad-mcp\logs` fallback).
3. **CUA config port mismatch** — `scripts/cua-nsis-config.json` `backend_port` must be `11966` (patched) but double-check `cua-smoke.py` reads it.
4. If the log shows the backend `EADDRINUSE` or dying, capture by running `resources\qcad-mcp-backend.exe --mode http --port 11966` manually — should print `Uvicorn running on http://127.0.0.1:11966` (freecad's backend did this in 10s).

## Next step
1. Read `%LOCALAPPDATA%\ai.fleet.qcad-mcp\logs\backend-spawn.log` (or `%LOCALAPPDATA%\QCAD MCP\logs\`).
2. If cold-start: raise `MAX_RETRY`/poll window in `cua-smoke.py` OR add a `--no-banner`/prewarm; if spawn-path: match freecad's `materialize_backend` (dev path vs resource).
3. Then run `mcpb pack` (85-tool equivalent) + commit + push + write `.assess-fix-timestamp`.

## Files changed this session
- `native/src/main.rs`, `native/src/backend.rs` (port 11966 + Docker-safe `free_port` + spawn/lifecycle)
- `run_server.py`, `src/qcad_mcp/server.py` (Gate J isatty + http force)
- `qcad-mcp-backend.spec` (opentelemetry hiddenimports)
- 22 doc/config files: `10966→11966`, `10967→11967`
- `scripts/cua-nsis-config.json` (port 11966)
- `mcp-central-docs/operations/WEBAPP_PORTS.md` (11966/11967)
- Removed `src-tauri/` (backed up)
