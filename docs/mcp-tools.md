# MCP Tools

All 15 tools registered via `@mcp.tool()` in `src/qcad_mcp/server.py`.

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
| **`qcad_status`** | READ_ONLY | QCAD Pro install/version/running status |
| **`plan_script`** | MUTATING | Execute ECMAScript against DXF via QCAD Pro |
| **`plan_render`** | MUTATING | High-fidelity SVG/PDF/BMP via QCAD Pro engine |
| **`plan_exec`** | MUTATING | Execute ECMAScript in running QCAD Pro GUI |

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

Execute ECMAScript in the running QCAD Pro GUI for live visual feedback.

```python
await plan_exec(code='''
var di = EAction.getDocumentInterface();
var doc = di.getDocument();
print("Current document has " + doc.queryAllEntities().length + " entities");
''')
# {"success": true, "data": {"stdout": "...", "stderr": "..."}}
```

Requires QCAD Pro GUI to be open with a document loaded. Changes affect the live document.
