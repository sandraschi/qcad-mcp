# QCAD MCP — User Guide

## Quick Start

### Prerequisites

- Python 3.10 or later
- Git
- (Optional) QCAD Pro 3.x for advanced tools

### Installation

```bash
# Clone the repository
git clone https://github.com/sandraschi/qcad-mcp.git
cd qcad-mcp

# Create virtual environment and install dependencies
uv sync

# Start the server (stdio mode for Claude Desktop / Cursor)
uv run python -m qcad_mcp.server

# Or start with HTTP transport (for webapp)
$env:MCP_TRANSPORT = "http"
uv run python -m qcad_mcp.server
```

### Connecting Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "qcad-mcp": {
      "command": "uv",
      "args": ["run", "--directory", "D:\\Dev\\repos\\qcad-mcp", "python", "-m", "qcad_mcp.server"],
      "env": {
        "QCAD_PRO_PATH": "C:\\Program Files\\QCAD"
      }
    }
  }
}
```

### Connecting Cursor

In Cursor Settings → MCP → Add Server:

```
Name: qcad-mcp
Type: stdio
Command: uv run --directory D:\Dev\repos\qcad-mcp python -m qcad_mcp.server
```

### Verifying Installation

```python
# Call this to verify the server is running
await qcad_status()
# Expected: {"success": true, "data": {"installed": ..., "running": ..., "version": ..., "install_dir": ...}}

# Check QCAD Pro availability
await plan_depot()
# Expected: {"success": true, "data": {"files": []}}
```

### Uploading Your First DXF

Upload via the REST API:

```bash
curl -X POST -F "file=@floorplan.dxf" http://localhost:10966/api/v1/upload
```

Or use `plan_create` to make one from scratch:

```python
await plan_create(
    filename="my_first_plan.dxf",
    entities=[
        {"type": "rect", "x": 0, "y": 0, "w": 10000, "h": 8000, "layer": "Walls"},
    ],
    description="My first floor plan - 10m x 8m"
)
```

---

## Tutorials

### Tutorial 1: Open a DXF and Get Info

Every CAD workflow starts with understanding what is in the drawing. Use `plan_info` to read DXF metadata.

```python
# Upload first, then inspect
await plan_info(file_name="floorplan.dxf")
```

Returns:
```json
{
  "success": true,
  "data": {
    "layers": ["Walls", "Doors", "Windows", "Furniture", "Labels"],
    "entity_counts": {"LINE": 152, "LWPOLYLINE": 34, "INSERT": 12, "CIRCLE": 8, "TEXT": 5},
    "bounding_box": {"xmin": 0, "ymin": 0, "xmax": 15000, "ymax": 12000},
    "block_count": 4,
    "dxf_version": "AC1027"
  }
}
```

Key things to look for:
- **Layers**: Lists all layers in the drawing. Identify which layers contain walls, dimensions, annotations.
- **Entity counts**: Reveals the composition. Many LINE entities on wall layers = good candidate for extrusion.
- **Bounding box**: Drawing extent in mm. A 15000x12000 bounding box = 15m x 12m floor plan.
- **Blocks**: Door and window block definitions. INSERT entities reference these.
- **DXF version**: AC1027 = AutoCAD 2013 format.

Now that you understand the drawing structure, you can decide next steps: preview as SVG, analyse rooms, add dimensions, or extrude to 3D.

### Tutorial 2: Preview a Floor Plan as SVG

Before making changes, generate a visual preview.

```python
# Full drawing preview with white background
await plan_to_svg(file_name="floorplan.dxf", background="#ffffff")

# Selective layer preview — walls and windows only
await plan_to_svg(
    file_name="floorplan.dxf",
    layers=["Walls", "Windows"],
    background="#1a1a1a",
    output_name="walls_only.svg"
)
```

The SVG is saved to `%LOCALAPPDATA%\qcad-mcp\output\output.svg` (or your custom name). Access it via:

```
http://localhost:10966/api/v1/download/output.svg
```

Layer filtering is useful for debugging — if the extrusion fails, render just the wall layers to check they contain valid LINE/LWPOLYLINE entities. SVG background colours: use `"white"` for print-style previews, `"black"` or `"#1a1a1a"` for web-style dark mode.

### Tutorial 3: Extrude a Floor Plan to 3D STL

The signature workflow: take a 2D DXF floor plan and turn it into a 3D mesh.

```python
# Basic extrusion (3m walls, 0.3m thick)
await plan_extrude(file_name="floorplan.dxf")

# Custom extrusion for a residential plan
await plan_extrude(
    file_name="floorplan.dxf",
    wall_height=2.5,       # 2.5m ceiling height
    wall_thickness=0.24,   # 240mm standard brick wall
    wall_layers=["Walls", "Interior Walls"],
    output_name="residential_walls.stl"
)

# Commercial building with thicker walls
await plan_extrude(
    file_name="commercial_plan.dxf",
    wall_height=4.0,
    wall_thickness=0.4,
    wall_layers=["Structural Walls"],
)
```

The STL is a binary mesh file ready for:
- **3D printing**: Import into PrusaSlicer or Bambu Studio for physical scale models
- **Game engines**: Import into Unity3D, Godot, or Unreal Engine as environment geometry
- **FreeCAD**: Use `mesh_to_solid` to convert to a B-Rep solid for BIM operations
- **Resonite / VRChat**: Import as world geometry

After extrusion, check the result:
```python
await model_info(file_name="residential_walls.stl")
# {"success": true, "data": {"type": "stl", "vertices": 1008, "facets": 2016}}
```

If extrusion returns no walls, verify that your DXF has LINE or LWPOLYLINE entities on layers whose names contain "wall", "mauer", or "wand". You can override with explicit `wall_layers`:

```python
# Fallback: try all layers
await plan_extrude(file_name="floorplan.dxf", wall_layers=["0", "Walls", "ARCHITECTURE"])
```

### Tutorial 4: Detect Rooms in a Floor Plan

Analyse a floor plan for room detection, area calculation, and door/window identification.

```python
await plan_analyse(file_name="floorplan.dxf")
```

Sample output:
```json
{
  "success": true,
  "data": {
    "rooms": [
      {"layer": "Walls", "area_m2": 45.6, "perimeter_m": 26.4, "vertex_count": 4, "likely_type": "room"},
      {"layer": "Walls", "area_m2": 32.1, "perimeter_m": 22.8, "vertex_count": 4, "likely_type": "room"},
      {"layer": "Walls", "area_m2": 18.3, "perimeter_m": 16.9, "vertex_count": 6, "likely_type": "room"}
    ],
    "doors_windows": [
      {"block": "DOOR", "layer": "Doors", "position": {"x": 5000, "y": 3000}},
      {"block": "WINDOW", "layer": "Windows", "position": {"x": 12000, "y": 4000}}
    ],
    "total_entities": 5,
    "wall_length_m": 45.2
  }
}
```

Room detection logic:
1. Finds closed LWPOLYLINE entities
2. Calculates area using the shoelace formula (converted from mm^2 to m^2)
3. Calculates perimeter in metres
4. Classifies as "wall_outline" if the layer name suggests walls, or "room" otherwise
5. Sorts rooms by area descending (largest room first)

Door/window detection:
- Searches for INSERT block entities whose name contains: door, window, porte, porta, fenster, fenetre, finestra, tu__r
- Returns block name, layer, and insertion point coordinates

This analysis helps with space planning, area calculations for building regulations, and quantity takeoffs.

### Tutorial 5: Search and Download CAD Blocks

Build a library of architectural blocks for use in your drawings.

```python
# Search for furniture blocks
await plan_blocks(query="sofa", category="furniture")

# Browse floor plans
await plan_blocks(category="floor-plans", limit=5)

# Search for kitchen elements
await plan_blocks(query="kitchen")

# Search across all categories
await plan_blocks(query="desk")
```

Results include title, author, source (cadblocksfree, biblocad, or gallery), download URL, thumbnail URL, category, and download/like counts.

Once you find a block, download it:

```python
# Download a sofa block
await plan_blocks_download(
    title="Sofa Collection",
    source="cadblocksfree",
    url="https://www.cadblocksfree.com/sofa_collection.dxf"
)

# Download a sample floor plan
await plan_blocks_download(
    title="Residential Floor Plan",
    source="biblocad",
    url="https://biblocad.com/downloads/residential_plan.dxf"
)
```

After download, inspect the block:

```python
await plan_info(file_name="Sofa_Collection.dxf")
await plan_to_svg(file_name="Sofa_Collection.dxf", background="#ffffff")
```

Blocks saved to the depot can be inserted into any drawing using `plan_block_insert`.

### Tutorial 6: Convert DWG to DXF

When you receive drawings in AutoCAD DWG format, convert them to DXF for processing with QCAD MCP tools.

```python
# Convert DWG to DXF
await plan_convert(file_name="floorplan.dwg")
# Returns: {"success": true, "filename": "floorplan.dxf", "format": "DXF"}

# Convert to a specific output name
await plan_convert(
    file_name="architectural.dwg",
    output_name="architectural_2024.dxf"
)

# Convert DXF to DWG (for AutoCAD users)
await plan_convert(
    file_name="processed_plan.dxf",
    output_name="processed_plan.dwg"
)
```

Requirements:
- QCAD Pro 3.x must be installed (set `QCAD_PRO_PATH` environment variable)
- Input and output must be `.dxf` or `.dwg` extensions
- The converted file is saved to the depot and immediately available for other tools

After conversion, verify the result:

```python
await plan_info(file_name="floorplan.dxf")
await plan_to_svg(file_name="floorplan.dxf")
```

### Tutorial 7: Add Dimensions to a Drawing

Add professional dimensions to your floor plan using QCAD Pro.

```python
# Aligned dimensions for wall lengths
await plan_dimension(file_name="floorplan.dxf", dimensions=[
    {"type": "aligned", "x1": 0, "y1": 0, "x2": 5000, "y2": 0, "xd": 2500, "yd": -500},
    {"type": "aligned", "x1": 0, "y1": 0, "x2": 0, "y2": 4000, "xd": -500, "yd": 2000},
    {"type": "aligned", "x1": 5000, "y1": 0, "x2": 5000, "y2": 4000, "xd": 5500, "yd": 2000},
    {"type": "aligned", "x1": 0, "y1": 4000, "x2": 5000, "y2": 4000, "xd": 2500, "yd": 4500},
])

# Radial dimension for a column
await plan_dimension(file_name="floorplan.dxf", dimensions=[
    {"type": "radial", "cx": 2500, "cy": 2000, "px": 2800, "py": 2000},
])

# Angular dimension
await plan_dimension(file_name="floorplan.dxf", dimensions=[
    {"type": "angular", "cx": 0, "cy": 0, "x1": 5000, "y1": 0, "x2": 0, "y2": 3000, "xd": 2000, "yd": -800},
])

# Full dimension set for a room
await plan_dimension(
    file_name="floorplan.dxf",
    dimensions=[
        {"type": "aligned", "x1": 0, "y1": 0, "x2": 8000, "y2": 0, "xd": 4000, "yd": -600},
        {"type": "aligned", "x1": 8000, "y1": 0, "x2": 8000, "y2": 6000, "xd": 8600, "yd": 3000},
        {"type": "aligned", "x1": 0, "y1": 6000, "x2": 8000, "y2": 6000, "xd": 4000, "yd": 6600},
        {"type": "aligned", "x1": 0, "y1": 0, "x2": 0, "y2": 6000, "xd": -600, "yd": 3000},
    ],
    output_name="fully_dimensioned.dxf"
)
```

Dimension types:
- **aligned**: Linear dimension parallel to the measured line
- **rotated**: Linear dimension at a specified angle
- **radial**: Radius dimension (from centre to point on circle)
- **diametric**: Diameter dimension (through centre)
- **angular**: Angle dimension between two lines

For aligned dimensions, `x1/y1` and `x2/y2` are the extension line origins (the points being measured). `xd/yd` is the position of the dimension line text. A negative `yd` places the dimension below the measured line.

### Tutorial 8: Describe a Floor Plan in Natural Language

Use AI-powered generation to create CAD drawings from plain English descriptions.

```python
# Create a simple rectangular plan
await plan_agentic(goal="Create a rectangular floor plan 10m x 8m with 4 equal rooms, label them, add aligned dimensions on all sides")

# Add a door to each room
await plan_agentic(goal="Add a 1m door to the south wall of each room", file_name="floorplan.dxf")

# Create a studio apartment layout
await plan_agentic(goal="Create a 6m x 5m studio apartment with a 3m x 4m main room, a 2m x 2m bathroom, and a 2m x 1m kitchenette. Label each area. Add dimensions on all external walls.")

# Create an office layout
await plan_agentic(goal="Design a 12m x 8m open office with 6 workstations (2m x 1.5m each), a meeting room (4m x 3m), and a kitchenette (3m x 2m). Add dimensions and labels.")
```

How it works:
1. The goal is sent to the connected LLM via MCP sampling
2. The LLM generates QCAD Pro ECMAScript code
3. The code is executed via `plan_script` against a new or existing document
4. Results are returned with entity count and step information

If AI sampling is unavailable (e.g., running on a basic MCP client), the server falls back to template-based generation for common patterns like rectangles, circles, and dimensions.

After agentic generation, review the output:

```python
await plan_info(file_name="agentic_output.dxf")
await plan_to_svg(file_name="agentic_output.dxf", background="#ffffff")
```

### Tutorial 9: Run a Beam Structural Analysis

Analyse the structural capacity of beams using direct stiffness FEM.

```python
# Simply supported concrete beam, 5m span, 10kN point load at midspan
await plan_beam_analysis(
    beams=[{
        "x1": 0, "y1": 0,
        "x2": 5000, "y2": 0,
        "height": 400,    # 400mm deep
        "width": 200,     # 200mm wide
        "E": 25000        # C25/30 concrete
    }],
    supports=[
        {"node_index": 0, "location": "start", "dof": "x,y"},  # pinned
        {"node_index": 0, "location": "end", "dof": "y"},      # roller
    ],
    loads=[{
        "type": "point",
        "beam_index": 0,
        "position": 0.5,   # midspan
        "magnitude": 10    # 10 kN
    }]
)
```

Sample output:
```json
{
  "success": true,
  "data": {
    "node_count": 2,
    "beam_count": 1,
    "nodes": [{"x": 0, "y": 0}, {"x": 5000, "y": 0}],
    "beams": [{
      "beam_index": 0,
      "length_m": 5.0,
      "max_moment_kNm": 12.5,
      "max_shear_kN": 5.0,
      "axial_force_kN": 0,
      "max_deflection_mm": 3.12,
      "max_stress_mpa": 4.69,
      "material_mpa": 25000,
      "section_mm": "200x400",
      "ok": true
    }],
    "reactions": [
      {"node": 0, "dof": "Fy", "reaction_N": 5000},
      {"node": 1, "dof": "Fy", "reaction_N": 5000}
    ]
  }
}
```

Multi-beam examples:

```python
# Two-span continuous beam with distributed load
await plan_beam_analysis(
    beams=[
        {"x1": 0, "y1": 0, "x2": 4000, "y2": 0, "height": 500, "width": 300, "E": 25000},
        {"x1": 4000, "y1": 0, "x2": 9000, "y2": 0, "height": 500, "width": 300, "E": 25000},
    ],
    supports=[
        {"node_index": 0, "location": "start", "dof": "x,y"},
        {"node_index": 0, "location": "end", "dof": "y"},
        {"node_index": 1, "location": "end", "dof": "y"},
    ],
    loads=[
        {"type": "distributed", "beam_index": 0, "magnitude": 15},
        {"type": "point", "beam_index": 1, "position": 0.5, "magnitude": 25},
    ]
)

# Steel beam with 6m span
await plan_beam_analysis(
    beams=[{
        "x1": 0, "y1": 0, "x2": 6000, "y2": 0,
        "height": 300, "width": 150,
        "E": 210000     # structural steel
    }],
    supports=[
        {"node_index": 0, "location": "start", "dof": "x,y"},
        {"node_index": 0, "location": "end", "dof": "y"},
    ],
    loads=[
        {"type": "point", "beam_index": 0, "position": 0.33, "magnitude": 20},
        {"type": "point", "beam_index": 0, "position": 0.67, "magnitude": 15},
    ]
)
```

Understanding the results:
- **max_moment_kNm**: Peak bending moment. Used for reinforcement design in concrete or section selection in steel.
- **max_shear_kN**: Peak shear force. Determines shear reinforcement requirements.
- **axial_force_kN**: Compression or tension along the beam axis. Non-zero in framed structures.
- **max_deflection_mm**: Vertical displacement. Check against span/250 (typical serviceability limit).
- **max_stress_mpa**: Extreme fibre bending stress. For concrete: should be under tensile strength; for steel: under 355 MPa (S355).
- **ok**: Rough safety check (stress < E/15). For concrete C25/30 (E=25000), limit is ~1667 MPa — bending stress will almost always pass. For design-level checks, use this as a screening tool.

### Tutorial 10: Export Wall Data for FreeCAD BIM

Extract wall geometry from a DXF floor plan as structured data, then pass it to freecad-mcp for BIM creation.

```python
# Step 1: Extract wall data
result = await plan_wall_data(
    file_name="floorplan.dxf",
    wall_layers="Walls, Exterior Walls, Interior Walls"
)
```

Result:
```json
{
  "success": true,
  "data": {
    "wall_count": 18,
    "total_length_m": 45.2,
    "walls": [
      {"type": "line", "x1": 0, "y1": 0, "x2": 10000, "y2": 0, "length_mm": 10000, "angle_deg": 0, "layer": "walls"},
      {"type": "line", "x1": 10000, "y1": 0, "x2": 10000, "y2": 8000, "length_mm": 8000, "angle_deg": 90, "layer": "walls"},
      {"type": "polyline_seg", "x1": 0, "y1": 0, "x2": 0, "y2": 8000, "length_mm": 8000, "angle_deg": 90, "layer": "walls"}
    ]
  }
}
```

Then, with freecad-mcp connected, create BIM walls:

```python
# For each wall segment, create a BIM wall
wall_data = result["data"]["walls"]

for w in wall_data:
    length_mm = w["length_mm"]
    await freecad_bim_create_wall(
        length_mm=length_mm,
        width_mm=240,           # wall thickness
        height_mm=3000,         # wall height
        placement_x=w["x1"],
        placement_y=w["y1"],
        rotation_z=w["angle_deg"]
    )
```

The complete BIM pipeline from DXF to IFC:

```python
# 1. Extract wall data from DXF
wall_result = await plan_wall_data(file_name="floorplan.dxf", wall_layers="Walls")

# 2. Extrude to STL for 3D model
await plan_extrude(file_name="floorplan.dxf", wall_height=3.0, wall_thickness=0.3)

# 3. Convert STL to FreeCAD solid (via freecad-mcp)
await freecad_mesh_to_solid(file_name="extruded.stl")

# 4. Export to IFC (via freecad-mcp)
await freecad_bim_export_ifc(file_name="building.fcstd")
```

This pipeline enables a complete DXF-to-BIM workflow: take an existing 2D CAD drawing and produce a full 3D BIM model with parametric wall objects, material properties, and IFC output for coordination with architects and structural engineers.

### Tutorial 11: Measure Entities in a Drawing

Get precise measurements of all entities using QCAD Pro's geometry engine.

```python
await plan_measure(file_name="floorplan.dxf")
```

Returns per-entity data:
```json
{
  "success": true,
  "data": {
    "entity_count": 42,
    "total_line_length": 15200,
    "total_area": 48000000,
    "entities": [
      {"type": "line", "length": 5000, "angle_deg": 0, "x1": 0, "y1": 0, "x2": 5000, "y2": 0},
      {"type": "circle", "radius": 200, "center_x": 2500, "center_y": 2000, "area": 125663, "circumference": 1256.6},
      {"type": "arc", "radius": 800, "center_x": 4000, "center_y": 3000, "start_angle": 0, "end_angle": 90},
      {"type": "polyline", "vertex_count": 4, "closed": true, "length": 14200},
      {"type": "text", "text": "Living Room", "height": 250},
      {"type": "dimension"},
      {"type": "hatch"},
      {"type": "block_ref"}
    ]
  }
}
```

Measurement details:
- **Lines**: Length, angle, start/end coordinates
- **Circles**: Radius, centre, area, circumference
- **Arcs**: Radius, centre, start/end angles
- **Polylines**: Vertex count, closed/open state, total length
- **Splines**: Identified but not measured (polynomial complexity)
- **Text**: Text content and height
- **Blocks**: Identified as block references (custom content unknown without dissection)

### Tutorial 12: Add Text Labels and Hatch Patterns

Annotate your floor plan with room labels and material hatches.

```python
# Add room labels
await plan_text(
    file_name="floorplan.dxf",
    texts=[
        {"text": "Living Room", "x": 2500, "y": 3000, "height": 300, "halign": "center", "layer": "Labels"},
        {"text": "Kitchen", "x": 7000, "y": 5000, "height": 300, "halign": "center", "bold": true, "layer": "Labels"},
        {"text": "Bedroom 1", "x": 2500, "y": 7000, "height": 250, "halign": "center", "layer": "Labels"},
        {"text": "Bathroom", "x": 7000, "y": 1000, "height": 250, "halign": "center", "italic": true, "layer": "Labels"},
        {"text": "NORTH", "x": 7500, "y": 7800, "height": 200, "rotation": 0, "halign": "center", "layer": "Labels"},
    ],
    output_name="labelled_plan.dxf"
)

# Add material hatches
await plan_hatch(
    file_name="labelled_plan.dxf",
    hatches=[
        # Concrete fill for structural walls
        {"points": [[0,0], [10000,0], [10000,8000], [0,8000]], "pattern": "AR-CONC", "scale": 0.5},
        # Earth fill for garden area
        {"points": [[0,0], [3000,0], [3000,2000], [0,2000]], "pattern": "EARTH", "scale": 1.0, "angle": 45},
        # Solid colour for a specific room
        {"points": [[4000,1000], [5000,1000], [5000,2000], [4000,2000]], "pattern": "SOLID", "color": "#FFE4B5"},
    ],
    output_name="hatched_plan.dxf"
)
```

Text styling options:
- **height**: Text height in drawing units (typically mm)
- **halign**: "left", "center", "right" — horizontal alignment
- **valign**: "top", "middle", "bottom", "baseline" — vertical alignment
- **rotation**: Degrees of rotation (0 = horizontal, 90 = vertical upward)
- **bold**, **italic**: Font styling

Hatch patterns available: ANSI31-38 (general purpose engineering), AR-CONC (concrete), AR-HBONE (horizontal bone), AR-BRSTD (brick/standard), SOLID (solid fill), EARTH (earth/soil), GRASS, GRAVEL, LINE.

### Tutorial 13: Insert Block References

Add doors, windows, furniture, and fixtures using block symbols.

```python
# Insert standard doors
await plan_block_insert(
    file_name="floorplan.dxf",
    inserts=[
        {"block_name": "DOOR", "x": 2000, "y": 0, "rotation": 0},
        {"block_name": "DOOR", "x": 7000, "y": 0, "rotation": 0},
        {"block_name": "DOOR", "x": 2500, "y": 4000, "rotation": 90},
    ],
    output_name="doors_added.dxf"
)

# Insert windows with array
await plan_block_insert(
    file_name="doors_added.dxf",
    inserts=[
        {"block_name": "WINDOW", "x": 1000, "y": 4000, "scale_x": 0.8, "scale_y": 0.8, "rotation": 0},
        {"block_name": "WINDOW", "x": 3000, "y": 4000},
        {"block_name": "WINDOW", "x": 5000, "y": 4000},
        {"block_name": "WINDOW", "x": 7000, "y": 4000},
    ],
    output_name="windows_added.dxf"
)

# Insert furniture row (array pattern)
await plan_block_insert(
    file_name="floorplan.dxf",
    inserts=[
        {"block_name": "DESK", "x": 500, "y": 500, "columns": 4, "col_spacing": 2000, "rows": 2, "row_spacing": 1500},
    ],
    output_name="furniture_added.dxf"
)
```

Block insert supports array parameters (`columns`, `rows`, `col_spacing`, `row_spacing`) for efficient placement of repeated elements like desks, chairs, or cubicles.

### Tutorial 14: Create Arrays of Entities

Create repeating patterns for grids, columns, and bolt patterns.

```python
# Rectangular array — column grid
await plan_array(
    file_name="column.dxf",
    pattern="rectangular",
    count=6,
    params={"dx": 3000, "dy": 3000},
    output_name="column_grid.dxf"
)

# Polar array — radial furniture arrangement
await plan_array(
    file_name="chair.dxf",
    pattern="polar",
    count=8,
    params={"cx": 0, "cy": 0, "angle": 360},
    output_name="round_table_seating.dxf"
)

# Partial polar array
await plan_array(
    file_name="window.dxf",
    pattern="polar",
    count=4,
    params={"cx": 2500, "cy": 2000, "angle": 180},
    output_name="curved_windows.dxf"
)
```

### Tutorial 15: Modify and Clean Up a Drawing

Clean up a DXF by deleting, renaming, and reorganising layers.

```python
# Delete all text entities
await plan_modify(
    file_name="floorplan.dxf",
    operations=[{"op": "delete", "type_filter": "TEXT"}]
)

# Delete entities on a specific layer
await plan_modify(
    file_name="floorplan.dxf",
    operations=[{"op": "delete", "layer_filter": "Furniture"}]
)

# Rename layers
await plan_modify(
    file_name="floorplan.dxf",
    operations=[
        {"op": "layer-rename", "old_name": "A-WALL", "new_name": "Walls"},
        {"op": "layer-rename", "old_name": "A-DOOR", "new_name": "Doors"},
        {"op": "layer-rename", "old_name": "A-GLAZ", "new_name": "Windows"},
    ]
)

# Merge two layers
await plan_modify(
    file_name="floorplan.dxf",
    operations=[
        {"op": "merge-layers", "source": "Walls-Ext", "target": "Walls"},
        {"op": "merge-layers", "source": "Walls-Int", "target": "Walls"},
    ]
)

# Freeze and lock layers
await plan_modify(
    file_name="floorplan.dxf",
    operations=[
        {"op": "layer-freeze", "layer_filter": "Furniture"},
        {"op": "layer-lock", "layer_filter": "Labels"},
    ]
)
```

Multiple operations can be chained in a single call. They are applied in order.

### Tutorial 16: Search and Run ECMAScript Scripts

Discover and execute reusable QCAD automation scripts from the built-in gallery.

```python
# Step 1: Search for scripts related to drawing
await plan_scripts_search(query="rectangle", source="gallery")

# Search across all sources
await plan_scripts_search(query="dimension", source="all")

# Browse by category
await plan_scripts_search(category="utility", limit=10)

# Step 2: Download a script to the depot
await plan_scripts_download(
    title="Door Swing Arc",
    source="gallery",
    url="gallery://door_swing.js"
)
# Returns: {"success": true, "filename": "Door Swing Arc.js", "content": "// Door Swing Arc..."}

# Step 3: Execute the downloaded script against a drawing
await plan_script(
    code=downloaded_content,          # the script content from step 2
    file_name="floorplan.dxf",
    output_name="with_door_swing.dxf"
)

# Or use plan_exec for quick prototyping
await plan_exec(code="document.queryAllEntities().length;", file_name="floorplan.dxf")
```

The gallery includes 12 pre-curated scripts: Rectangle Generator, Door Swing Arc, Auto-Dimension Polyline, Layer Report, Room Area Labels, Batch DXF to SVG, Merge Layers, Grid Generator, Entity Counter, Wall Centerline, Scale Drawing, and Rotate Selection. Each can be downloaded and executed without network access.

### Tutorial 17: Create a Drawing From Scratch with Scripts

Use `plan_script` for complex procedural generation beyond what `plan_create` primitives offer.

```python
# Generate a grid of columns (5x4 grid at 3m spacing)
await plan_script(code="""
var op = new RAddObjectsOperation();
for (var col = 0; col < 5; col++) {
    for (var row = 0; row < 4; row++) {
        var cx = col * 3000;
        var cy = row * 3000;
        op.addObject(new RCircleEntity(document,
            new RCircleData(new RVector(cx, cy), 150)));
        op.addObject(new RTextEntity(document,
            new RTextData(new RVector(cx - 100, cy - 200), 150, 0,
                "C" + (col+1) + "-" + (row+1),
                "Standard", 0, 0, 0, 0, 0, 0, false, false, 0, false, false)));
    }
}
op.apply(document);
""", output_name="column_grid.dxf")

# Label all rooms in a floor plan
await plan_script(code="""
var ents = document.queryAllEntities();
var op = new RAddObjectsOperation();
var roomCount = 0;
for (var i = 0; i < ents.length; i++) {
    var e = document.queryEntity(ents[i]);
    if (!e || !(e instanceof RPolylineEntity)) continue;
    var verts = e.getData().getVertices();
    if (verts.length < 3) continue;
    var cx = 0, cy = 0;
    for (var j = 0; j < verts.length; j++) {
        cx += verts[j].getX();
        cy += verts[j].getY();
    }
    cx /= verts.length;
    cy /= verts.length;
    roomCount++;
    op.addObject(new RTextEntity(document,
        new RTextData(new RVector(cx, cy), 250, 0,
            "Room " + roomCount,
            "Standard", 1, 0, 0, 0, 0, 0, true, false, 0, false, false)));
}
op.apply(document);
print("Labelled " + roomCount + " rooms");
""", file_name="floorplan.dxf", output_name="labelled_rooms.dxf")
```

The ECMAScript API gives you access to QCAD Pro's full entity model. Key classes available: RAddObjectsOperation (batch entity creation), RModifyObjectsOperation (entity property changes), RDeleteObjectsOperation (entity removal), RLineEntity, RCircleEntity, RArcEntity, RPolylineEntity, RSplineEntity, RTextEntity, RDimAlignedEntity, RDimRadialEntity, RHatchEntity, RBlockReferenceEntity, RLayer, RColor, RVector.

---

## REST API Reference

All REST endpoints are available at `http://localhost:10966/api/v1/`.

### Depot Management

```bash
# List all files
curl http://localhost:10966/api/v1/depot

# Upload a file
curl -X POST -F "file=@floorplan.dxf" http://localhost:10966/api/v1/upload

# Download a file
curl http://localhost:10966/api/v1/download/floorplan.dxf -o floorplan.dxf

# Update metadata
curl -X PUT -H "Content-Type: application/json" \
  -d '{"description": "Office floor plan rev 3", "tags": ["office", "ground-floor"]}' \
  http://localhost:10966/api/v1/depot/floorplan.dxf

# Delete a file
curl -X DELETE http://localhost:10966/api/v1/depot/floorplan.dxf
```

### Server Status

```bash
# Health check
curl http://localhost:10966/health

# Full status with QCAD Pro availability
curl http://localhost:10966/api/v1/status
```

### Webapp

The QCAD MCP webapp (port 10967) provides a graphical interface for all CAD operations. Access it at `http://localhost:10967` after starting the server with HTTP transport. The React dashboard includes:

- **File Browser**: Browse, upload, download, and delete depot files with metadata
- **SVG Preview**: Visualise DXF drawings directly in the browser with layer selection
- **STL Viewer**: 3D preview of extruded models using Three.js
- **Analysis Console**: Room detection results, beam analysis outputs, and wall data viewer
- **Tool Explorer**: Full list of all 26 MCP tools with parameter documentation and live test console
- **Settings**: QCAD Pro path configuration, depot directory, and server restart

Start the webapp alongside the backend via `start.ps1` or run just the backend and use the REST API directly.

---

## Troubleshooting

### Common Issues

**"QCAD Pro required" error**
Tools like `plan_script`, `plan_dimension`, `plan_measure`, `plan_text`, `plan_hatch`, `plan_block_insert`, `plan_array`, `plan_wall_data`, `plan_agentic`, and `plan_transpile` require QCAD Pro 3.x. Either:
- Install QCAD Pro and set `QCAD_PRO_PATH`
- Stick with core tools that only need ezdxf

**"No wall entities found" from plan_extrude**
The DXF has no LINE or LWPOLYLINE entities on layers whose names match "wall", "mauer", or "wand". Either:
- Check layer names with `plan_info`
- Specify explicit `wall_layers` parameter
- Check that entities are on those layers (not on layer "0")

**"File not found in depot"**
Upload the file first via `POST /api/v1/upload` or use `plan_create` to generate one.

**QCAD Pro not detected**
- Verify `QCAD_PRO_PATH` points to the QCAD install directory (not the qcad.exe binary)
- Check `qcadcmd.com` exists in that directory
- Restart the MCP server after setting the env var

**plan_agentic returns template-based output instead of AI-generated**
- The AI sampling feature requires a sampling-capable MCP client (Claude Desktop, Cursor with agent mode)
- Without sampling, plan_agentic falls back to simple rectangle/circle templates
- For best results, use plan_agentic from a client that supports `ctx.sample()`

**plan_transpile produces empty or wrong output**
- Complex AutoLISP patterns may not be recognised by the heuristic fallback
- Always try with AI sampling enabled for accurate translation
- If the AutoLISP uses custom commands (defun C:XXX), those may reference AutoCAD-only features that have no QCAD equivalent

**DWG conversion fails**
- Verify QCAD Pro is installed (plan_convert requires it)
- Check that the DWG file is not password-protected or encrypted
- Some newer DWG formats (2024+) may need a QCAD Pro update
- Use ODA File Converter as a free alternative for DWG to DXF

**SVG appears blank**
- Check background colour — black background with black lines is invisible
- Use `layers` parameter to filter to known layers
- Verify the DXF has entities (check with `plan_info`)

### FAQ

**Q: Can I use this without QCAD Pro?**
A: Yes. Core tools (plan_info, plan_to_svg, plan_extrude, plan_export, plan_analyse, plan_create, plan_depot) work with ezdxf alone. The 4 Pro tools (qcad_status, plan_script, plan_render, plan_exec) and all 8 annotation tools require QCAD Pro.

**Q: What DXF versions are supported?**
A: R12 through R2018 (AC1009–AC1027). Binary and ASCII DXF both work.

**Q: Can I convert DWG files?**
A: Yes, via `plan_convert` which requires QCAD Pro. Alternatively, use the free ODA File Converter to convert DWG to DXF first.

**Q: How do I get files into the depot?**
A: Three ways: (1) REST API upload (`POST /api/v1/upload`), (2) `plan_create` to generate a new DXF, (3) `plan_blocks_download` to import from a web library.

**Q: What units does qcad-mcp use?**
A: All coordinates are in millimetres. Drawings in metres are converted assuming 1 metre = 1000 mm. Areas are reported in m^2 by plan_analyse.

**Q: Can I run structural analysis without QCAD Pro?**
A: Yes! `plan_beam_analysis` is a pure Python FEM implementation with no external dependencies.

**Q: How do I export a plan to PDF?**
A: Two options: `plan_export(file_name="plan.dxf", format="pdf")` (uses ezdxf fallback if QCAD Pro unavailable) or `plan_render(file_name="plan.dxf", format="pdf")` (QCAD Pro only, higher fidelity).

**Q: What is the wall data format for freecad-mcp integration?**
A: Each wall segment is a dict: `{"x1": float, "y1": float, "x2": float, "y2": float, "length_mm": float, "angle_deg": float, "layer": str}`. Pass each segment to `bim_create_wall()`.

**Q: How is the STL mesh generated?**
A: Each wall line segment is offset by half the wall thickness on each side, creating a rectangular cross-section, then extruded vertically to the wall height. The resulting 6-sided box is triangulated into 12 triangles per segment.

**Q: Are there any file size limits?**
A: The depot REST API accepts files up to 50 MB. Very large DXF files (100k+ entities) may slow down ezdxf operations. For large files, QCAD Pro is recommended.

**Q: What is a block vs an entity vs a layer?**
A: Layers organise drawing content by type. Entities are geometric objects (lines, circles, text) on layers. Blocks are reusable symbol definitions (door, window, furniture) stored once in the block table and inserted as block references (INSERT entities) multiple times. Modifying a block definition updates all its insertions.

**Q: Can qcad-mcp handle 3D DXF files?**
A: QCAD MCP is primarily a 2D tool. 3D DXF entities (3DFACE, 3DSOLID, MESH) are not supported by ezdxf or QCAD Pro's 2D workflow. For 3D DXF handling, use freecad-mcp or Blender.

**Q: How do I share files between qcad-mcp and freecad-mcp?**
A: Two pipelines exist: (1) plan_extrude produces STL files in the output directory that freecad-mcp's mesh_to_solid can read; (2) plan_wall_data produces structured JSON wall data that can be iterated to call freecad-mcp's bim_create_wall for each segment. Ensure both servers can access the same depot directory or transfer files via HTTP download/upload.
