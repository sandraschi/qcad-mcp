# MCP Tools

All 7 tools registered via `@mcp.tool()` in `src/qcad_mcp/server.py`.

| Tool | Annotation | Description |
|:---|:---|:---|
| `plan_info` | READ_ONLY | DXF metadata: layers, entity counts, bounding box |
| `plan_to_svg` | MUTATING | DXF → SVG preview with layer filtering |
| `plan_extrude` | MUTATING | DXF walls → 3D STL mesh |
| `plan_export` | MUTATING | DXF → SVG/PNG/PDF |
| `plan_analyse` | READ_ONLY | Room detection, area, door/window identification |
| `plan_create` | MUTATING | Create DXF from primitives |
| `plan_depot` | READ_ONLY | List files in the depot |

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
