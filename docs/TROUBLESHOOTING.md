# Troubleshooting — qcad-mcp

## Backend won't start / port busy

`start.ps1` (fleet engine) clears zombies on 11966/11967 first. Manual:
check `Get-NetTCPConnection -LocalPort 11966`. Docker Desktop squats
10960–11000 on some hosts — this repo already moved to 11966/11967.

## QCAD Pro tools fail

1. `qcad_status` (MCP) or `/api/v1/status` (REST) — installed? running?
2. Set `QCAD_PRO_PATH` if auto-detect misses (`C:\Program Files\QCAD`).
3. Headless/Tauri (`QCAD_TAURI=1`) never auto-launches the GUI — start QCAD
   manually. DWG convert/render/script tools need the GUI reachable.

## Empty STL from plan_extrude

Wall-layer auto-detect looks for wall/mauer/wand/mur/parete/pared. Pass
`wall_layers=["<exact>"]` explicitly when names differ. Verify with
`plan_info` (entity counts) + `plan_to_svg` first.

## DWG without QCAD Pro

ezdxf reads DXF only. Convert needs QCAD Pro (`plan_convert`). No free
in-repo path — use docs/floorplan-sources.md raster→DXF pipeline instead.

## Webapp shows "unreachable" but backend curls fine

Browser CORS path vs curl path. Prod builds must use same-origin `/api`
(vite proxy in dev); absolute `http://127.0.0.1:11966` works only from
localhost tabs — fixed in `webapp/src/lib/api.ts` (Tauri gate). Verify:
foreign-Origin request must return `Access-Control-Allow-Origin`.

## CI red on clean checkout, green locally

Untracked source files (services/, utils/) — commit everything; CI has no
Goliath disk state. Stage-all rule: never end a session dirty.

## NSIS smoke: backend not reachable after install

Cold start (matplotlib + ezdxf import of the 54 MB backend) can exceed the
smoke poll window. Run `resources\qcad-mcp-backend.exe --mode http --port
11966` manually — expect `Uvicorn running` in ~10 s — then raise the poll
window in `scripts/cua-smoke.py`. See HANDOVER.md 2026-09-01.

## Live multi-document bridge (macOS proposal, issue #1)

Deferred — macOS-only validation, no PR attached. See
docs/live-bridge-proposal.md. `plan_exec`/`plan_script` cover depot-file
scripting today.
