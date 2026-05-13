# MCP Tools

All 20 tools registered via `@mcp.tool()` in `src/qcad_mcp/server.py`.

| Tool | Annotation | Description |
|:---|:---|:---|
| `plan_info` | READ_ONLY | DXF metadata: layers, entity counts, bounding box |
| `plan_to_svg` | MUTATING | DXF → SVG preview with layer filtering (ezdxf) |
| `plan_extrude` | MUTATING | DXF walls → 3D STL mesh |
| `plan_export` | MUTATING | DXF → SVG/PNG/PDF (QCAD Pro preferred, ezdxf fallback) |
| `plan_analyse` | READ_ONLY | Room detection, area, door/window identification |
| `plan_create` | MUTATING | Create DXF from primitives |
| `plan_depot` | READ_ONLY | List files in the depot |
| `plan_convert` | MUTATING | DWG↔DXF conversion via QCAD Pro |
| `plan_modify` | MUTATING | Modify entities/layers (delete, offset, rename, freeze, etc.) |
| `plan_blocks` | READ_ONLY | Search CAD block libraries |
| `plan_blocks_download` | MUTATING | Download CAD blocks to depot |
| `qcad_status` | READ_ONLY | QCAD Pro install/version/running status |
| `plan_script` | MUTATING | Execute arbitrary ECMAScript against DXF |
| `plan_render` | MUTATING | High-fidelity SVG/PDF/BMP via QCAD Pro engine |
| `plan_exec` | MUTATING | Quick ECMAScript execution, no file I/O |
| `plan_dimension` | MUTATING | Add aligned/radial/angular dimensions |
| `plan_agentic` | MUTATING | NL goal → ECMAScript → executed |
| `plan_measure` | READ_ONLY | Per-entity distance/angle/area measurement |
| `plan_text` | MUTATING | Text annotations with height/alignment/rotation |
| `plan_hatch` | MUTATING | Hatch/fill patterns to closed regions |

---

## plan_info

Read a DXF file and return metadata. Call this first to understand what's in the drawing.

```python
await plan_info(file_name="floorplan.dxf")
# {"success": true, "data": {
#   "layers": ["Walls", "Windows", "Furniture"],
#   "entity_counts": {"LINE": 152, "LWPOLYLINE": 34, "INSERT": 12},
#   "bbox": {"xmin": 0, "ymin": 0, "xmax": 15000, "ymax": 12000},
#   "blocks": ["DOOR", "WINDOW", "SINK"],
#   "dxf_version": "AC1027"
# }}
```

Returns: layers, entity counts by type, bounding box in drawing units, block names, DXF version.

---

## plan_to_svg

Render a DXF as an SVG for browser preview. Supports optional layer filtering.

```python
# All layers
await plan_to_svg(file_name="floorplan.dxf")
# {"success": true, "output": "floorplan.svg", "data": {"layers": 5, "entities": 246}}

# Specific layers only
await plan_to_svg(file_name="floorplan.dxf", layers="Walls,Windows", background="#ffffff")
```

Returns SVG file path and entity/layer counts. The SVG is served via `GET /api/v1/download/{filename}`.

---

## plan_extrude

The killer feature — extrude wall entities to 3D and export as STL.

```python
await plan_extrude(
    file_name="floorplan.dxf",
    wall_height=3.0,       # metres
    wall_thickness=0.3,    # metres
    layer_filter="Walls",  # comma-separated layer names
)
# {"success": true, "output": "floorplan.stl",
#  "data": {"walls": 42, "vertices": 1008, "faces": 2016, "size_kb": 156.2}}
```

Finds LINE and LWPOLYLINE entities on specified layers, offsets them by wall thickness, extrudes to wall height, and triangulates into an STL mesh.

---

## plan_export

Export DXF to different output formats.

```python
# SVG (uses ezdxf + matplotlib)
await plan_export(file_name="floorplan.dxf", format="svg")

# PNG
await plan_export(file_name="floorplan.dxf", format="png", dpi=300)

# PDF (uses QCAD Pro CLI if available, else matplotlib fallback)
await plan_export(file_name="floorplan.dxf", format="pdf")
```

When QCAD Pro is installed (via `QCAD_PRO_PATH`), PDF export uses the native QCAD renderer for higher fidelity.

---

## plan_analyse

Detect rooms, calculate areas, and identify doors/windows.

```python
await plan_analyse(file_name="floorplan.dxf")
# {"success": true, "data": {
#   "wall_length_m": 45.2,
#   "rooms": [
#     {"layer": "Walls", "type": "polyline", "area_m2": 24.5, "perimeter_m": 18.2, "vertices": 4}
#   ],
#   "doors_windows": [
#     {"block": "DOOR", "layer": "Doors", "position": {"x": 5000, "y": 3000}}
#   ]
# }}
```

Room detection finds closed LWPOLYLINE entities (wall loops) and calculates their area and perimeter. Doors and windows are identified by block INSERT entities with matching name patterns.

---

## plan_create

Create a new DXF from scratch using geometric primitives.

```python
await plan_create(
    output_name="new_plan.dxf",
    entities=[
        {"type": "rect", "layer": "Walls", "x1": 0, "y1": 0, "x2": 10000, "y2": 8000},
        {"type": "line", "layer": "Walls", "x1": 5000, "y1": 0, "x2": 5000, "y2": 8000},
        {"type": "circle", "layer": "Columns", "cx": 2500, "cy": 4000, "r": 200},
        {"type": "text", "layer": "Labels", "x": 100, "y": 100, "text": "Living Room", "height": 500},
    ],
)
# {"success": true, "filename": "new_plan.dxf", "entities": 4}
```

Supports: `line`, `rect`, `circle`, `text`, `polyline`.

---

## plan_depot

List all DXF files in the depot with metadata.

```python
await plan_depot()
# {"success": true, "files": [
#   {"name": "floorplan.dxf", "size_kb": 124.5, "meta": {"title": "Office Layout", "author": "Architect"}}
# ]}
```

Each file may have a JSON metadata sidecar (`.meta.json`) created or updated via the depot REST API.

---

## QCAD Pro Tools (requires QCAD Pro)

These tools require QCAD Pro 3.x installed and reachable. Check availability with `qcad_status` first.

### qcad_status

Check QCAD Pro installation and running state.

```python
await qcad_status()
# {"success": true, "data": {
#   "installed": true,
#   "running": true,
#   "version": "3.32.9",
#   "install_dir": "C:\\Program Files\\QCAD"
# }}
```

### plan_script

Execute arbitrary ECMAScript against a DXF document. Full access to QCAD API.

```python
# Create a circle in a new document
await plan_script(
    code='''
var op = new RAddObjectsOperation();
op.addObject(new RCircleEntity(document, new RCircleData(new RVector(50, 50), 25)));
op.apply(document);
''',
    output_name="circle.dxf"
)
# {"success": true, "data": {"entity_count": 1, "layers": ["0"], "errors": []}}

# Modify an existing file
await plan_script(
    code='''
var op = new RModifyObjectsOperation();
var layer = new RLayer(document, "Annotations", false, false, new RColor("blue"));
op.addObject(layer);
op.apply(document);
''',
    file_name="floorplan.dxf",
    output_name="floorplan_annotated.dxf"
)
```

User code has access to `document` (RDocument), `di` (RDocumentInterface), and the full QCAD + Qt ECMAScript API.

### plan_render

High-fidelity DXF/DWG rendering via QCAD Pro's native engine.

```python
await plan_render(file_name="floorplan.dxf", format="svg")
# {"success": true, "output": "floorplan.svg", "data": {"size_kb": 45.2}}

await plan_render(file_name="floorplan.dxf", format="pdf", output_name="A1_export.pdf")
# {"success": true, "output": "A1_export.pdf", "data": {"size_kb": 128.7}}
```

Supports SVG, PDF, and BMP. Renders hatches, TrueType fonts, lineweights, and dimensions correctly — superior to the ezdxf+matplotlib fallback.

### plan_exec

Quick ECMAScript execution in a temporary QCAD Pro session — no file I/O overhead.

```python
await plan_exec(code='''
var op = new RAddObjectsOperation();
op.addObject(new RCircleEntity(document, new RCircleData(new RVector(10,10), 5)));
op.apply(document);
''')
# {"success": true, "data": {"entity_count": 1, "layers": ["0"], "errors": []}}

# Load a depot file and query
await plan_exec(code='''
var ents = document.queryAllEntities();
print("Found " + ents.length + " entities");
''', file_name="floorplan.dxf")
```

Use for quick queries, prototyping, or lightweight modifications. For operations that need output saved, use `plan_script` instead.

### plan_dimension

Add dimension entities to a drawing — aligned, radial, diametric, angular, rotated.

```python
await plan_dimension(file_name="floorplan.dxf", dimensions=[
    {"type": "aligned", "x1": 0, "y1": 0, "x2": 5000, "y2": 0, "xd": 2500, "yd": -500},
    {"type": "radial", "cx": 2500, "cy": 2000, "px": 2800, "py": 2000},
    {"type": "angular", "cx": 0, "cy": 0, "x1": 5000, "y1": 0, "x2": 0, "y2": 3000, "xd": 2000, "yd": -800},
], output_name="dimensioned.dxf")
```

### plan_agentic

Multi-step CAD workflow from a natural language goal. Generates ECMAScript, executes it, returns results.

```python
await plan_agentic(goal="Create a rectangular floor plan 10m x 8m with 4 equal rooms, add dimensions on all sides")
# {"success": true, "output": "agentic_output.dxf", "data": {"steps": 1, "entity_count": 12}}

await plan_agentic(goal="Add a 1m door to the south wall of each room", file_name="floorplan.dxf")
```

Uses AI sampling when available (via `ctx: Context`). Falls back to template-based generation for common patterns (rectangles, circles).

### plan_measure

Precise per-entity measurements via QCAD Pro's geometry engine.

```python
await plan_measure(file_name="floorplan.dxf")
# {"success": true, "data": {
#   "entity_count": 42,
#   "total_line_length": 15200,
#   "total_area": 48000000,
#   "entities": [
#     {"type": "line", "length": 5000, "angle_deg": 0, "x1": 0, "y1": 0, "x2": 5000, "y2": 0},
#     {"type": "circle", "radius": 200, "center_x": 2500, "center_y": 2000, "area": 125663}
#   ]
# }}
```

Detects lines, arcs, circles, polylines, splines, text, dimensions, hatches, block refs via `instanceof`.

### plan_text

Add text annotations with full styling control.

```python
await plan_text(file_name="floorplan.dxf", texts=[
    {"text": "Living Room", "x": 2500, "y": 3000, "height": 250, "halign": "center"},
    {"text": "Kitchen", "x": 6000, "y": 2000, "height": 250, "layer": "Labels", "bold": True},
    {"text": "North", "x": 4000, "y": 7800, "height": 200, "rotation": 90, "halign": "center"},
], output_name="annotated.dxf")
```

Supports height, alignment (left/center/right, top/middle/bottom/baseline), rotation (degrees), bold, italic.

### plan_hatch

Add hatch/fill patterns to closed polygon regions.

```python
await plan_hatch(file_name="floorplan.dxf", hatches=[
    {"points": [[0,0], [5000,0], [5000,4000], [0,4000]], "pattern": "AR-CONC", "scale": 0.5},
    {"points": [[1000,1000], [2000,1000], [2000,2000], [1000,2000]], "pattern": "SOLID"},
    {"points": [[3000,1000], [4000,1000], [3500,2000]], "pattern": "ANSI31", "angle": 45},
], output_name="hatched.dxf")
```

Available patterns: ANSI31-38, AR-CONC, AR-HBONE, AR-BRSTD, SOLID, EARTH, GRASS, GRAVEL, LINE.
