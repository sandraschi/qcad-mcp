# QCAD MCP — System Prompt

## Overview

QCAD MCP is a Model Context Protocol server that provides CAD (Computer-Aided Design) operations through MCP tools, REST API, and a React webapp. It bridges the gap between natural-language AI agents and the QCAD Pro / ezdxf ecosystem for 2D floor plan creation, annotation, conversion, 3D extrusion, and structural analysis.

- **Repository**: sandraschi/qcad-mcp
- **Ports**: Backend 10966, Frontend 10967
- **Version**: 0.4.0 (26 tools)
- **License**: MIT

## Architecture

### Core Engine — ezdxf

The foundational DXF parsing and generation is powered by **ezdxf** (Python). All core tools (plan_info, plan_to_svg, plan_extrude, plan_export, plan_analyse, plan_create, plan_depot) work with ezdxf alone — no external CAD software required. This means basic floor plan operations work out of the box after `uv sync`.

### Optional Accelerator — QCAD Pro

For advanced operations (ECMAScript execution, high-fidelity rendering, dimensioning, wall data extraction, beam analysis), QCAD Pro 3.x must be installed. The `QCAD_PRO_PATH` environment variable points to the QCAD install directory. When QCAD Pro is available, tools like `plan_render`, `plan_script`, `plan_dimension`, `plan_measure`, `plan_text`, `plan_hatch`, `plan_block_insert`, `plan_array`, `plan_wall_data`, `plan_agentic`, and `plan_transpile` become available. Check availability with `qcad_status()`.

### Dual Transport

The server supports stdio (Claude Desktop, Cursor) and HTTP (MCP streamable HTTP at `/mcp`). The HTTP transport also serves a REST API at `/api/v1/` and a React webapp frontend.

### File Depot

All DXF, DWG, SVG, and STL files are stored in a persistent directory:
- `%LOCALAPPDATA%\qcad-mcp\depot` — DXF/DWG source files
- `%LOCALAPPDATA%\qcad-mcp\output` — generated SVGs, PDFs, STLs, rendered exports

Files are uploaded via `POST /api/v1/upload` and downloaded via `GET /api/v1/download/{filename}`. The depot persists across server restarts. Depot metadata (descriptions, tags, entity counts) is stored as JSON sidecar files.

### Version Support

DXF format support: R12 through R2018 (AC1009–AC1027). Both ASCII and binary DXF. DWG support via QCAD Pro conversion only.

## MCP Tool Reference (26 Tools)

### Core Tools (7)

#### `plan_info`
Read a DXF file from the depot and return metadata.

Parameters:
- `file_name` (str, required) — DXF filename in the depot, e.g. `"floorplan.dxf"`

Return: `{"success": bool, "data": {"layers": [...], "entity_counts": {...}, "bounding_box": {...}, "block_count": int}}`

`layers` is a list of layer names present in the drawing. `entity_counts` maps DXF entity type strings (LINE, LWPOLYLINE, CIRCLE, ARC, TEXT, INSERT, etc.) to counts. `bounding_box` has xmin, ymin, xmax, ymax in drawing units (typically mm). `block_count` is the number of block definitions. `dxf_version` is the ACAD version code.

Call this first on any uploaded DXF to understand what layers and entities exist.

#### `plan_to_svg`
Convert a DXF file to an SVG preview image using ezdxf's matplotlib backend.

Parameters:
- `file_name` (str, required) — DXF filename in the depot
- `output_name` (str, default `"output.svg"`) — desired output SVG filename
- `layers` (list[str] | None, default None) — optional list of layer names to include; all layers if omitted
- `background` (str, default `"white"`) — background colour: `"white"`, `"black"`, or hex e.g. `"#1a1a1a"`

Return: `{"success": bool, "output": str, "data": {"size_kb": float}}`

The SVG is saved to the output directory and served via `GET /api/v1/download/{output_name}`. Layer filtering enables selective focus (e.g. walls only, furniture only).

#### `plan_extrude`
Extrude wall entities from a DXF floor plan into a 3D STL mesh.

Parameters:
- `file_name` (str, required) — DXF filename in the depot
- `output_name` (str, default `"extruded.stl"`) — desired output STL filename
- `wall_height` (float, default 3.0) — wall extrusion height in metres
- `wall_thickness` (float, default 0.3) — wall thickness in metres
- `wall_layers` (list[str] | None, default None) — layer names to treat as walls. Auto-detected if omitted (matches layer names containing "wall", "mauer", "wand", "mur", "parete", "pared")

Return: `{"success": bool, "output": str, "data": {"vertices": int, "faces": int, "wall_count": int, "size_kb": float, "wall_height_m": float, "wall_thickness_m": float}}`

Finds LINE and LWPOLYLINE entities on wall layers, offsets them by wall_thickness on each side, extrudes vertically to wall_height, and triangulates into a binary STL mesh. The STL can be downloaded and imported into freecad-mcp (mesh_to_solid), Blender, Unity3D, Resonite, or slicer software for 3D printing.

#### `plan_export`
Export a DXF file to SVG, PDF, or PNG.

Parameters:
- `file_name` (str, required) — DXF filename in the depot
- `format` (str, default `"svg"`) — output format: `"svg"`, `"pdf"`, or `"png"`
- `output_name` (str, default `""`) — output filename; auto-generated if empty

Return: `{"success": bool, "output": str, "data": {"size_kb": float, "backend": str}}`

Tries QCAD Pro for high-fidelity SVG and PDF output when available. Falls back to ezdxf + matplotlib for all formats. For guaranteed QCAD Pro rendering, use `plan_render` instead.

#### `plan_analyse`
Analyse a DXF floor plan: detect rooms, calculate areas, identify doors and windows.

Parameters:
- `file_name` (str, required) — DXF filename in the depot

Return: `{"success": bool, "data": {"rooms": [...], "doors_windows": [...], "total_entities": int, "wall_length_m": float}}`

Room detection finds closed LWPOLYLINE entities (wall loops/room outlines) and calculates their area and perimeter. Rooms are sorted by area descending. Door and window INSERT block entities are identified by name patterns ("door", "window", "porte", "porta", "fenster", "fenetre", "finestra", "tu__r"). Total wall length sums LINE and LWPOLYLINE edge lengths converted to metres.

#### `plan_create`
Create a new DXF file from geometric primitives and store it in the depot.

Parameters:
- `filename` (str, required) — output filename (must end in `.dxf`)
- `entities` (list[dict], required) — list of entity dicts. Supported types:
  - `line`: `{"type": "line", "x1": 0, "y1": 0, "x2": 100, "y2": 0, "layer": "walls"}`
  - `rect`: `{"type": "rect", "x": 10, "y": 10, "w": 80, "h": 60, "layer": "rooms"}`
  - `circle`: `{"type": "circle", "cx": 50, "cy": 50, "r": 20, "layer": "columns"}`
  - `text`: `{"type": "text", "x": 50, "y": 50, "content": "Label", "height": 5, "layer": "labels"}`
  - `polyline`: `{"type": "polyline", "points": [[0,0], [100,0], [100,50], [0,50]], "closed": true, "layer": "walls"}`
- `layers` (list[dict] | None, default None) — optional layer definitions: `[{"name": "walls", "color": 7}, ...]`
- `description` (str, default `""`) — optional description stored in depot metadata

Return: `{"success": bool, "filename": str, "data": {"size_kb": float, "entity_count": int}}`

Creates a new R2010-format DXF. Layers are auto-created from entity references if not explicitly defined. Colors use AutoCAD colour indices (1=red, 2=yellow, 3=green, 4=cyan, 5=blue, 6=magenta, 7=white/black).

#### `plan_depot`
List all CAD files in the persistent depot with metadata.

Parameters: None

Return: `{"success": bool, "data": {"files": [{"name": ..., "size_kb": ..., "modified": ..., "meta": {...}}]}}`

Each file entry includes name, size in KB, last modified date, and optional metadata (description, tags, entity count). Metadata is stored as JSON sidecar files and can be updated via the REST API.

### Modify Tools (2)

#### `plan_convert`
Convert a CAD file between DWG and DXF formats using QCAD Pro CLI.

Parameters:
- `file_name` (str, required) — DWG or DXF filename in the depot
- `output_name` (str, default `""`) — output filename, must end in `.dxf` or `.dwg`

Return: `{"success": bool, "filename": str, "format": str}`

Requires QCAD Pro installed at `QCAD_PRO_PATH`. Converts DWG to DXF for processing with ezdxf tools, or DXF to DWG for AutoCAD compatibility. The converted file is saved to the depot.

#### `plan_modify`
Modify entities and layers in a DXF/DWG file.

Parameters:
- `file_name` (str, required) — DXF or DWG filename in the depot
- `operations` (list[dict], required) — list of modification operations. Each dict:
  - `op`: operation type — `"delete"`, `"offset"`, `"layer-set-color"`, `"layer-rename"`, `"layer-freeze"`, `"layer-thaw"`, `"layer-lock"`, `"layer-unlock"`, `"merge-layers"`
  - `type_filter`: optional DXF type filter (e.g. `"LINE"`, `"CIRCLE"`, `"TEXT"`)
  - `layer_filter`: optional layer name filter
  - `color`: colour index for `layer-set-color`
  - `distance`: offset distance in drawing units for `offset`
  - `source` / `target`: source and target layer names for `merge-layers`
  - `old_name` / `new_name`: old/new layer names for `layer-rename`

Return: `{"success": bool, "operations": int, "summary": [str, ...]}`

Operations are applied in order. The file is saved back to the depot after all operations complete.

### QCAD Pro Tools (4)

#### `qcad_status`
Check QCAD Pro installation status, version, and capabilities.

Parameters: None

Return: `{"success": bool, "data": {"installed": bool, "running": bool, "version": str, "install_dir": str}}`

Call this first before using any QCAD Pro-dependent tools to verify availability.

#### `plan_script`
Execute arbitrary ECMAScript in QCAD Pro against a DXF document.

Parameters:
- `code` (str, required) — ECMAScript code to execute. Variables `document` (RDocument) and `di` (RDocumentInterface) are pre-bound.
- `file_name` (str, default `""`) — optional DXF/DWG filename in depot to load before execution
- `output_name` (str, default `"script_output.dxf"`) — output filename saved to output directory

Return: `{"success": bool, "data": {"entity_count": int, "layer_count": int, "layers": [...], "errors": [...], "output_file": str}}`

Full access to the QCAD ECMAScript API: RAddObjectsOperation, RLineEntity, RCircleEntity, RArcEntity, RVector, RPolylineEntity, RTextEntity, RDimAlignedEntity, RHatchEntity, RBlockReferenceEntity, RLayer, RModifyObjectsOperation, and the full Qt API. All entity creation must be grouped in a single RAddObjectsOperation followed by `op.apply(document)`. Print output is captured via `print()` calls.

#### `plan_render`
High-fidelity rendering of a DXF/DWG via QCAD Pro's native engine.

Parameters:
- `file_name` (str, required) — DXF/DWG filename in the depot
- `format` (str, default `"svg"`) — output format: `"svg"`, `"pdf"`, or `"bmp"`
- `output_name` (str, default `""`) — output filename, auto-generated from input name if empty

Return: `{"success": bool, "output": str, "data": {"size_kb": float}}`

Renders hatches, TrueType fonts, dimension styles, and lineweights correctly — superior to the ezdxf+matplotlib fallback used by plan_export. Requires QCAD Pro installed.

#### `plan_exec`
Execute ECMAScript in a temporary QCAD Pro session without file I/O overhead.

Parameters:
- `code` (str, required) — ECMAScript snippet to execute against a temporary document
- `file_name` (str, default `""`) — optional depot filename to load before execution

Return: `{"success": bool, "data": {"entity_count": int, "layers": [...], "errors": [...]}}`

Use for quick queries, prototyping, or lightweight modifications. Faster startup than plan_script since no output file is saved.

### Annotation Tools (8)

#### `plan_dimension`
Add dimension entities to a DXF drawing using QCAD Pro.

Parameters:
- `file_name` (str, required) — DXF/DWG filename in the depot
- `dimensions` (list[dict], required) — list of dimension specs:
  - Aligned: `{"type": "aligned", "x1": 0, "y1": 0, "x2": 5000, "y2": 0, "xd": 2500, "yd": -500}`
  - Rotated: `{"type": "rotated", "x1": 0, "y1": 0, "x2": 5000, "y2": 0, "xd": 2500, "yd": -500, "angle": 45}`
  - Radial: `{"type": "radial", "cx": 2500, "cy": 2000, "px": 2800, "py": 2000}`
  - Diametric: `{"type": "diametric", "cx": 2500, "cy": 2000, "px": 2800, "py": 2000}`
  - Angular: `{"type": "angular", "cx": 0, "cy": 0, "x1": 5000, "y1": 0, "x2": 0, "y2": 3000, "xd": 2000, "yd": -800}`
- `output_name` (str, default `""`) — output filename, defaults to `<input>_dimensioned.dxf`

Return: `{"success": bool, "output": str, "data": {"entity_count": int, "dim_count": int}}`

#### `plan_measure`
Measure distances, angles, areas, and perimeters in a DXF drawing via QCAD Pro.

Parameters:
- `file_name` (str, required) — DXF/DWG filename in the depot

Return: `{"success": bool, "data": {"entity_count": int, "entities": [...], "total_line_length": float, "total_area": float}}`

Uses QCAD Pro's geometry engine via ECMAScript. Returns per-entity measurements: lines with length/angle/endpoints, arcs with radius/center/angles, circles with radius/area/circumference, polylines with vertex count/length/closed state, splines, text (content/height), dimensions, hatches, and block references.

#### `plan_text`
Add text annotations to a DXF drawing via QCAD Pro.

Parameters:
- `file_name` (str, required) — DXF/DWG filename in the depot
- `texts` (list[dict], required) — list of text annotations:
  - `text` (str, required) — text content
  - `x`, `y` (float, default 0) — position
  - `height` (float, default 5) — text height
  - `layer` (str, default `"0"`) — layer name
  - `rotation` (float, default 0) — rotation in degrees
  - `halign` (str, default `"left"`) — horizontal alignment: `"left"`, `"center"`, `"right"`
  - `valign` (str, default `"baseline"`) — vertical alignment: `"top"`, `"middle"`, `"bottom"`, `"baseline"`
  - `bold` (bool, default false)
  - `italic` (bool, default false)
- `output_name` (str, default `""`) — output filename, defaults to `<input>_annotated.dxf`

Return: `{"success": bool, "output": str, "data": {"entity_count": int, "text_count": int}}`

#### `plan_hatch`
Add hatch/fill patterns to closed regions in a DXF drawing via QCAD Pro.

Parameters:
- `file_name` (str, required) — DXF/DWG filename in the depot
- `hatches` (list[dict], required) — list of hatch specs:
  - `points` (list[list[float]], required) — closed polygon boundary: `[[x1,y1], [x2,y2], ...]`
  - `pattern` (str, default `"ANSI31"`) — pattern name
  - `scale` (float, default 1.0) — pattern scale
  - `angle` (float, default 0) — pattern rotation in degrees
  - `layer` (str, default `"0"`) — layer name
  - `color` (str, optional) — colour name or `#RRGGBB`

Available patterns: ANSI31-38, AR-CONC, AR-HBONE, AR-BRSTD, SOLID, EARTH, GRASS, GRAVEL, LINE
- `output_name` (str, default `""`) — output filename, defaults to `<input>_hatched.dxf`

Return: `{"success": bool, "output": str, "data": {"entity_count": int, "hatch_count": int}}`

#### `plan_block_insert`
Insert block references (doors, windows, furniture symbols) into a DXF drawing.

Parameters:
- `file_name` (str, required) — DXF/DWG filename in the depot
- `inserts` (list[dict], required) — list of block insertions:
  - `block_name` (str, required) — name of the block to insert
  - `x`, `y` (float) — insertion position
  - `scale_x`, `scale_y` (float, default 1.0) — scale factors
  - `rotation` (float, default 0) — rotation in degrees
  - `layer` (str, optional) — target layer
  - `columns`, `rows` (int, optional) — array parameters
  - `col_spacing`, `row_spacing` (float, optional) — array spacing
- `output_name` (str, default `""`) — output filename, defaults to `<input>_blocks.dxf`

Return: `{"success": bool, "output": str, "data": {"entity_count": int, "insert_count": int}}`

Blocks must exist in the drawing or be available in the depot. Use `plan_blocks` to search for block libraries and `plan_blocks_download` to import them.

#### `plan_array`
Create a rectangular or polar array of all entities in a drawing.

Parameters:
- `file_name` (str, required) — DXF/DWG filename in the depot
- `pattern` (str, required) — `"rectangular"` or `"polar"`
- `count` (int, required) — number of copies including the original
- `params` (dict, default `{}`):
  - Rectangular: `{"dx": 1000, "dy": 800}` (spacing in mm)
  - Polar: `{"cx": 50, "cy": 50, "angle": 360}` (centre point, total angle in degrees)
- `output_name` (str, default `""`) — output filename, defaults to `<input>_array.dxf`

Return: `{"success": bool, "output": str, "data": {"entity_count": int, "copies": int}}`

Useful for window grids, column grids, bolt patterns, radial furniture arrangements, and repeating architectural features.

#### `plan_wall_data`
Extract wall segment coordinates as structured BIM-ready JSON.

Parameters:
- `file_name` (str, required) — DXF/DWG filename in the depot
- `wall_layers` (str, default `""`) — comma-separated layer names. Empty = auto-detect layers containing "wall", "mauer", or "wand"
- `wall_thickness` (float, default 0.3) — default wall thickness in metres

Return: `{"success": bool, "data": {"wall_count": int, "total_length_m": float, "walls": [{"x1":.., "y1":.., "x2":.., "y2":.., "length_mm":.., "angle_deg":.., "layer":.., "type":..}]}}`

Each wall segment includes start/end coordinates, length in mm, angle in degrees, layer name, and segment type ("line" or "polyline_seg"). LWPOLYLINE entities on wall layers are decomposed into individual segments. The output is designed for direct consumption by freecad-mcp BIM tools: `plan_wall_data` output can be iterated to call `bim_create_wall` for each segment, creating an IFC-ready BIM model.

#### `plan_beam_analysis`
2D beam structural analysis using direct stiffness FEM.

Parameters:
- `beams` (list[dict], required) — list of beam segments:
  - `x1`, `y1`, `x2`, `y2` (float) — start and end coordinates in mm
  - `height` (float, default 300) — beam section height in mm
  - `width` (float, default 200) — beam section width in mm
  - `E` (float, default 25000) — elastic modulus in MPa (concrete = 25000, steel = 210000)
- `supports` (list[dict], default `[]`) — boundary conditions:
  - `node_index` (int) — beam segment index (0-based)
  - `location` (str) — `"start"` or `"end"` of the segment
  - `dof` (str) — comma-separated restrained DOFs: `"x,y,rz"` for fixed, `"x,y"` for pinned, `"y"` for roller
- `loads` (list[dict], default `[]`) — applied loads:
  - `type` (str) — `"point"` (kN) or `"distributed"` (kN/m)
  - `beam_index` (int) — beam segment index
  - `magnitude` (float) — force in kN (positive = downward)
  - For point loads: `position` (float, 0 to 1) — fraction along beam

Return: `{"success": bool, "data": {"node_count": int, "beam_count": int, "nodes": [...], "beams": [...], "reactions": [...]}}`

Each beam result includes: length in m, max bending moment in kNm, max shear in kN, axial force in kN, max deflection in mm, max stress in MPa, material modulus, section dimensions, and a safety check flag (`ok`). Supports pinned, fixed, roller supports and point, distributed loads.

### Agentic Tools (3)

#### `plan_agentic`
Multi-step CAD workflow from a natural-language goal. Uses AI sampling (MCP sampling) to decompose the goal into ECMAScript steps, then executes them sequentially via QCAD Pro.

Parameters:
- `goal` (str, required) — natural language CAD description, e.g. `"Create a rectangular floor plan 10m x 8m with 4 equal rooms, add dimensions on all sides"`
- `file_name` (str, default `""`) — optional depot file to work on (empty = create new document)
- `ctx` (Context, auto-injected) — MCP sampling context

Return: `{"success": bool, "output": str, "data": {"steps": int, "entity_count": int, "plan": [...]}}`

When AI sampling is available (Claude Desktop, Cursor), the goal is sent to the connected LLM which generates ECMAScript. Falls back to template-based generation for common patterns (rectangles, circles, dimensions) without AI.

#### `plan_transpile`
Translate AutoLISP to QCAD ECMAScript and execute the result.

Parameters:
- `lisp_code` (str, required) — AutoLISP code to translate
- `output_name` (str, default `"transpiled_output.dxf"`) — output filename
- `ctx` (Context, auto-injected) — MCP sampling context

Return: `{"success": bool, "output": str, "data": {"entity_count": int, "original_lisp": str, "transpiled_js": str, "source": str}}`

AI-powered transpiler that maps legacy AutoCAD AutoLISP routines to equivalent QCAD Pro ECMAScript. Handles entity creation (LINE, CIRCLE, ARC, RECTANG, PLINE, TEXT, HATCH, DIMLINEAR), layer operations, selection sets (ssget), math functions, control flow (if, repeat, foreach, while, defun), and coordinate transformations. Falls back to heuristic pattern matching for common structures when AI is unavailable.

#### `cad_sampling`
Use the host LLM (via MCP sampling) to reason about a CAD problem.

Parameters:
- `goal` (str, required) — the CAD/engineering question or operation to reason about
- `ctx` (Context, auto-injected) — MCP sampling context

Return: `{"success": bool, "response": str, "sampling_used": bool}`

Examples: "What material should I use for a bracket under 500N load?", "Plan the steps to convert a DXF to a 3D printable STL". Falls back to a static message if sampling is unavailable.

### Script Tools (2)

#### `plan_scripts_search`
Search QCAD ECMAScript libraries for reusable CAD scripts.

Parameters:
- `query` (str, default `""`) — search term for script title or description
- `category` (str, default `""`) — filter by category: drawing, modify, dimension, export, utility, block, layer, geometry
- `source` (str, default `"all"`) — source: gallery, gist, examples, or all
- `limit` (int, default 20) — max results

Return: `{"success": bool, "source": str, "results": [{"title": str, "description": str, "source": str, "url": str, ...}]}`

Searches three sources: the curated gallery (12 built-in scripts), GitHub Gist (community QCAD scripts), and QCAD Pro bundled example scripts (8 examples bundled with QCAD).

#### `plan_scripts_download`
Download an ECMAScript from a library to the local depot.

Parameters:
- `title` (str, required) — script title, used as filename
- `source` (str, required) — source from search results
- `url` (str, default `""`) — download URL, or `"gallery://id"` for local scripts

Return: `{"success": bool, "filename": str, "size_kb": float, "content": str}`

Gallery scripts (e.g. `"gallery://rectangle.js"`, `"gallery://door_swing.js"`) are served locally without network access. Downloaded scripts can be viewed, edited, or executed with `plan_script`.

### Block Tools (2)

#### `plan_blocks`
Search CAD block libraries for architectural blocks, furniture, doors, windows, and sample floor plans.

Parameters:
- `query` (str, default `""`) — search query (empty = browse all in category)
- `category` (str, default `""`) — category filter: furniture, doors-windows, kitchens, bathrooms, floor-plans
- `source` (str, default `"all"`) — source: cadblocksfree, biblocad, gallery, or all
- `limit` (int, default 20) — max results

Return: `{"success": bool, "results": list, "source": str}`

Results include title, author, thumbnail, download/like counts, category, and model URL.

#### `plan_blocks_download`
Download a CAD block from a library into the local depot.

Parameters:
- `title` (str, required) — block title (used as filename)
- `source` (str, required) — source from search results
- `url` (str, required) — download URL from search results

Return: `{"success": bool, "filename": str, "size_kb": float, "path": str}`

After download, use `plan_info` to inspect the block or `plan_to_svg` to preview it.

### Cross-Repo Fleet Integration

QCAD MCP integrates directly with **freecad-mcp** via two pipelines:

**Extrude Pipeline**: `plan_extrude(file_name="floorplan.dxf")` produces an STL mesh. That STL is consumed by freecad-mcp's `mesh_to_solid(file_name="extruded.stl")` which converts the triangular mesh to a FreeCAD B-Rep solid. The solid can then be used in BIM tools (`bim_create_wall`, `bim_create_slab`, `bim_create_window`, `bim_create_door`, `bim_export_ifc`).

**BIM Pipeline**: `plan_wall_data(file_name="floorplan.dxf")` extracts wall segment coordinates as structured JSON. Each wall segment can be passed to freecad-mcp's `bim_create_wall(length_mm=..., width_mm=..., height_mm=..., placement_x=..., placement_y=...)` to create parametric BIM wall objects with material, thickness, and height attributes. The resulting FCStd document can be exported to IFC format via `bim_export_ifc`.

### Prompts (3)

- `cad_expert(topic: str = "")` — CAD expertise and tool guidance. Returns a structured prompt for the LLM listing all tool categories and the depot CRUD API. Optional topic parameter for specific questions.
- `cad_analyse_plan(file_name: str)` — Floor plan analysis workflow: calls plan_info, plan_to_svg, plan_analyse in sequence and summarises results.
- `cad_extrude_3d(file_name: str, height: float = 3.0, thickness: float = 0.3)` — 3D extrusion workflow: runs plan_extrude with specified parameters and explains the output.

### Resources (2)

- `cad://depot` — List all files in the persistent CAD depot with metadata. Returns a formatted markdown list showing filename, size, modified date, description, tags, and entity count for each file.
- `cad://depot/{filename}` — Get information about a specific file in the depot. Returns JSON with name, size_kb, path, and metadata sidecar content.

### Configuration

| Env Variable | Default | Purpose |
|---|---|---|
| `QCAD_PRO_PATH` | `C:\Program Files\QCAD` | Path to QCAD Pro install directory |
| `QCAD_MCP_DEPOT` | `%LOCALAPPDATA%\qcad-mcp\depot` | CAD file storage directory |
| `QCAD_MCP_OUTPUT` | `%LOCALAPPDATA%\qcad-mcp\output` | Generated file output directory |

ezdxf version: latest (pip). Python 3.10+ required. QCAD Pro 3.x required for script, dimension, measure, text, hatch, block insert, array, wall data, agentic, and transpile tools.

### REST API

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/depot` | List all depot files with metadata |
| POST | `/api/v1/upload` | Upload a DXF/DWG file to the depot |
| GET | `/api/v1/download/{filename}` | Download a file from depot or output |
| PUT | `/api/v1/depot/{filename}` | Update file metadata |
| DELETE | `/api/v1/depot/{filename}` | Delete a file from depot |
| GET | `/api/v1/status` | Server status and QCAD Pro availability |
| GET | `/health` | Health check endpoint |

### Webapp

The React frontend (port 10967) provides a dashboard with 17 routes covering file browsing, SVG preview, 3D STL viewer, structural analysis results, and settings. The webapp uses the same REST API and reflects depot state in real time.
