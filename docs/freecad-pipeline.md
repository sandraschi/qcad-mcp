# QCAD MCP → FreeCAD MCP Pipeline

Cross-repo automated CAD pipeline: natural language to 2D floor plans to 3D BIM models.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        qcad-mcp (port 11966)                       │
│                                                                     │
│  plan_agentic("3-story apartment...")  ──→ DXF floor plan          │
│  plan_to_svg                           ──→ SVG 2D preview           │
│  plan_wall_data                        ──→ wall JSON [{x1,y1,...}] │
│  plan_extrude                          ──→ STL wall extrusion      │
│  plan_measure                          ──→ room areas, dimensions  │
│  plan_dimension / plan_text / plan_hatch → annotated drawing       │
└────────────────────────────────────────────────────────────────────┘
                │                               │
                ▼                               ▼
┌──────────────────────────────┐  ┌──────────────────────────────────┐
│     freecad-mcp (port 10944)  │  │     Resonite / Unity3D           │
│                               │  │                                  │
│  mesh_to_solid(STL→FCStd)     │  │  STL → static world mesh        │
│  bim_create_wall(wall JSON)   │  │  STL → interactive environment  │
│  bim_create_slab              │  │                                  │
│  bim_create_window/door       │  │     Blender / 3D Printing        │
│  bim_create_roof              │  │                                  │
│  bim_export_ifc → .ifc        │  │  STL → mesh optimization        │
│  bim_import_ifc → .ifc load   │  │  STL → PrusaSlicer → G-code     │
└──────────────────────────────┘  └──────────────────────────────────┘
```

## Demo Flow (NL → 2D → 3D → BIM → IFC)

Run this from the Webapp `/demo` page or via any MCP client:

### Step 1: Floor Plan (qcad-mcp)
```python
# Generate a floor plan from natural language
await plan_agentic(goal="3-story building, 2 apartments per floor, "
    "each with living room, bedroom, kitchen, bathroom, balcony. "
    "Rooftop garden. Lift shaft from ground to roof.")
# → outputs: building_agentic.dxf (or demo_123456.dxf from DemoPage)
```

### Step 2: 2D Preview (qcad-mcp)
```python
# Preview as SVG in browser
await plan_to_svg(file_name="demo_123456.dxf", output_name="preview.svg")
```

### Step 3: Extract Wall Data (qcad-mcp)
```python
# Get wall coordinates for freecad-mcp BIM tools
await plan_wall_data(file_name="demo_123456.dxf")
# Returns per-wall JSON: {x1,y1,x2,y2,length_mm,angle_deg,layer}
```

### Step 4: Extrude to 3D (qcad-mcp)
```python
# Generate 3D STL mesh for visualization
await plan_extrude(file_name="demo_123456.dxf", wall_height=3.0,
    output_name="walls.stl")
# The DemoPage shows this in an interactive Three.js viewer
```

### Step 5: Convert to Solid (freecad-mcp)
```python
# Convert STL mesh to FreeCAD B-Rep solid
await mesh_to_solid(file_name="walls.stl", output_name="walls_solid.fcstd")
```

### Step 6: Create BIM Elements (freecad-mcp)
```python
# Create parametric architectural walls from plan_wall_data
# Each wall segment from step 3 becomes a call:
await bim_create_wall(length_mm=5000, width_mm=240, height_mm=2800,
    placement_x=0, placement_y=0, rotation_z=0,
    output_name="wall_segment_1.fcstd")

# Floor slabs
await bim_create_slab(length_mm=12000, width_mm=10000, thickness=300,
    placement_z=0, output_name="ground_floor_slab.fcstd")

# Windows with auto-opening cuts
await bim_create_window(width=1200, height=1200,
    placement_x=2000, placement_y=0, wall_length=5000,
    window_type="casement", output_name="window_kitchen.fcstd")

# Doors with auto-opening cuts  
await bim_create_door(width=900, height=2100,
    placement_x=3000, placement_y=0, wall_length=8000,
    door_type="glass", output_name="door_entrance.fcstd")

# Roof
await bim_create_roof(length_mm=13000, width_mm=11000, angle_deg=15,
    output_name="roof.fcstd")
```

### Step 7: Export IFC (freecad-mcp)
```python
# Export as Industry Foundation Classes (architect-standard BIM format)
await bim_export_ifc(file_name="building.fcstd", output_name="building.ifc")
```

### Step 8: Import into Resonite / Unity3D
Upload the STL from step 4 directly into Resonite or Unity3D.
Or import the IFC from step 7 into any BIM software.

## Two Paths

| Path | When to Use | Tools |
|------|-------------|-------|
| **STL → mesh_to_solid** | Already have an STL (from plan_extrude or elsewhere) | `mesh_to_solid` → then any BIM creation |
| **Wall data → bim_create_wall** | Starting from a DXF floor plan, want parametric BIM walls | `plan_wall_data` + `bim_create_wall` per segment |

## Fleet Integration

| Repo | Pipeline | Port |
|------|----------|------|
| **qcad-mcp** | NL→DXF→SVG→STL→wall data | 11966 |
| **freecad-mcp** | STL→solid→BIM→IFC | 10944 |
| **resonite-mcp** | STL→XR world | 10978 |
| **unity3d-mcp** | STL→game engine | 10710 |
| **multi-backup-mcp** | Archive STL/FCStd/IFC outputs | 10798 |

## Tool Summary

### qcad-mcp (26 tools)
| Tool | Output | Feeds Into |
|------|--------|------------|
| `plan_agentic` | DXF | plan_to_svg, plan_extrude, plan_wall_data |
| `plan_to_svg` | SVG | Browser preview |
| `plan_extrude` | STL | mesh_to_solid, Resonite, Unity3D |
| `plan_wall_data` | JSON wall segments | bim_create_wall |
| `plan_measure` | room areas | — |
| `plan_dimension` / `plan_text` / `plan_hatch` | annotated DXF | — |

### freecad-mcp (21 tools)
| Tool | Input | Output |
|------|-------|--------|
| `mesh_to_solid` | STL | FCStd solid |
| `bim_create_wall` | params | FCStd Arch wall |
| `bim_create_slab` | params | FCStd BIM slab |
| `bim_create_window` | params | FCStd window (auto-cut) |
| `bim_create_door` | params | FCStd door (auto-cut) |
| `bim_create_roof` | params | FCStd roof |
| `bim_create_column` | params | FCStd column |
| `bim_export_ifc` | FCStd | IFC file |
| `bim_import_ifc` | IFC | FCStd |

