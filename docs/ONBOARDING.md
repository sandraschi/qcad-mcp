# Onboarding — qcad-mcp

First-timer path from zero to first STL. No account, no payment — only an
optional wrappee install.

## 1. Start (2 min, no QCAD needed)

```powershell
just bootstrap
start.ps1
```

Dashboard (http://127.0.0.1:11967) shows backend status + depot stats.
If the under-hero cue says QCAD Pro is missing, that is expected — the free
ezdxf engine already does preview, extrusion, analysis, and depot CRUD.

## 2. First drawing (3 min)

- Depot page → Create DXF wizard → draw a rectangle room on layer `Walls`.
- Viewer page → SVG preview with layer toggle.
- Analyse page → room area table.
- Extrude page → wall height 3.0 m, thickness 0.3 m → download STL.

Or via MCP: `plan_create` → `plan_to_svg` → `plan_extrude`.

## 3. Unlock QCAD Pro features (optional, paid wrappee)

Install QCAD Pro 3.x, set `QCAD_PRO_PATH` if outside `C:\Program Files\QCAD`,
restart the backend. The Dashboard cue clears automatically once
`qcad_status` reports installed. Unlocks: DWG convert, native render,
dimensions, hatches, text, arrays, block insert, full ECMAScript.

## 4. AI workflows

- Agentic page: NL → floor plan → SVG → STL (needs QCAD Pro for script steps).
- Pipeline page: 5-step wizard ending in FreeCAD wall-data export.
- Chat (FloatingChat): CAD expert via Ollama; providers in Settings.

## Sanity check

`plan_depot` returns ≥1 file, `plan_info` shows entity counts,
`/api/v1/health` returns 200. Mock state: none — Dashboard shows live
backend data only; an unreachable backend shows an explicit error, never
sample numbers.

## Pitfalls

- DWG files need QCAD Pro; without it stick to DXF.
- Coordinates are millimetres in depot files; extrusion height/thickness are
  metres in `plan_extrude` args.
- `plan_script` runs arbitrary ECMAScript with a 120 s timeout — dry-run
  snippets with `plan_exec` first.
