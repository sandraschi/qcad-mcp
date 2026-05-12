# qcad-mcp — 2D CAD MCP Server (DXF/DWG → SVG/STL)

**Vision**: Upload a floor plan DXF, preview it in the browser, extrude walls to 3D, import into Resonite/Unity3D. All through MCP tools.

**Price of entry**: €0 (Community Edition + `ezdxf`) or €50.40 (QCAD Pro for DWG + CLI tools).

---

## Architecture

```
DXF/DWG file
    │
    ├── ezdxf (pure Python, free) ──→ JSON entity list, layers, blocks
    │   ├── → SVG preview (webapp)
    │   └── → STL extrusion (walls → 3D)
    │
    └── QCAD CLI (Pro, €50) ──→ dwg2pdf, dwg2svg, dwg2bmp
        └── → high-fidelity rendering (text, hatches, dimensions)

MCP tools:
  plan_info       — layers, entities, block count, bounding box
  plan_to_svg     — DXF/DWG → preview SVG
  plan_extrude    — DXF/DWG → STL (walls extruded to height)
  plan_export     — DXF/DWG → PDF (via QCAD CLI, Pro only)
  plan_analyse    — room detection, area calculation, wall length
```

---

## Why `ezdxf` Is Enough

`ezdxf` is a mature pure-Python library (MIT license) that reads and writes DXF files from R12 to R2023. It handles:

- All entity types (lines, arcs, circles, polylines, lwpolylines, splines, hatches, texts, dimensions, blocks, inserts)
- Layers, blocks, linetypes, text styles
- DXF/DWG filter for reading
- SVG export (built-in, basic rendering)
- Geometry queries (bounding box, extents, selection)

What it doesn't do: render hatches perfectly, handle TrueType font paths, or reproduce QCAD's exact screen rendering. That's where QCAD Pro's CLI comes in if needed.

---

## MCP Tools

### plan_info
Read a DXF and return layer names, entity counts per type, bounding box, block definitions.

### plan_to_svg  
Convert DXF to SVG for browser preview. Uses `ezdxf`'s built-in SVG exporter with optional per-layer colour mapping. The webapp displays this in a viewer pane.

### plan_extrude
The killer feature. Takes a DXF floor plan, identifies closed polylines (walls, rooms), extrudes them to a configurable height (default 3m), and outputs an STL mesh. This STL can be:
- Loaded into the freecad-mcp Viz.tsx 3D viewer
- Imported into Resonite as a world
- Imported into Unity3D for physics

The extrusion logic: find all LWPOLYLINE/LINE entities on wall layers, offset them inward/outward for wall thickness, extrude vertically, boolean merge.

### plan_export
Pass through to QCAD Pro CLI if installed: `dwg2pdf`, `dwg2svg`, `dwg2bmp` for high-fidelity rendering.

### plan_analyse
Room detection: find enclosed polylines, label them as rooms, calculate area in m², identify doors/windows by block insertion.

---

## Webapp

Same fleet-standard Vite + React layout as freecad-mcp:

| Page | Purpose |
|------|---------|
| **Dashboard** | File counts, quick actions |
| **Viewer** | DXF upload + full-screen SVG preview with pan/zoom |
| **Extrude** | DXF → STL with wall height/thickness controls |
| **Analyse** | Room labels, area table, wall lengths |
| **Models** | Output STL browser, download |
| **Logs** | SSE log stream |
| **Settings** | QCAD Pro path, extrusion defaults |

The SVG viewer uses `react-svg-pan-zoom` or a simple `<object>` tag embedding the SVG. Layer toggle (show/hide layers) controlled by clicking layer names.

---

## Resonite Pipeline

```
qcad-mcp plan_extrude → STL
    │
    ├── freecad-mcp step_to_stl (optimise, decimate)
    │       │
    │       └── Resonite (import STL as static mesh)
    │
    └── Direct: Resonite supports STL import natively
```

The STL from `plan_extrude` is a 3D mesh of the floor plan. Import into Resonite as a static world object. Scale matches real-world dimensions (1 DXF unit = 1 metre by default).

---

## Fleet Registration

| Item | Value |
|------|-------|
| **Repo** | `D:\Dev\repos\qcad-mcp` |
| **Ports** | Backend 10966, Frontend 10967 |
| **DXF engine** | `ezdxf` (MIT, free) |
| **Optional** | QCAD Pro CLI (€50.40, for DWG/PDF) |

---

## Implementation Order

1. **Scaffold** — repo, FastMCP server, `ezdxf` integration, `plan_info` tool
2. **Viewer** — `plan_to_svg` + webapp viewer page with layer toggle
3. **Extrude** — `plan_extrude` → STL, the core feature
4. **Analyse** — `plan_analyse` with room/area detection
5. **QCAD Pro** — optional CLI integration for perfect PDF/DWG output
6. **Fleet standards** — docstrings, biome, tsc, ruff, justfile, ports, project page

Estimated effort: 6-10 hours over multiple sessions.
