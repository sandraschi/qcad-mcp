"""Dimension, measurement, text, and hatch annotation tools for QCAD MCP.

Tools that add intelligent annotation to DXF/DWG drawings via QCAD Pro's
ECMAScript engine: aligned/radial/diametric dimensions, geometry measurements,
text labels with full styling, and hatch/fill patterns.
"""

import os
from pathlib import Path
from typing import Annotated

from pydantic import Field

from qcad_mcp.config import DEPOT_DIR, OUTPUT_DIR
from qcad_mcp.services import qcad_pro
from qcad_mcp.services.qcad_pro import parse_marker

_README_ONLY = {"readonly": True}
_MUTATING = {}
_DIM_TYPE_MAP = {
    "aligned": "RDimAlignedEntity",
    "rotated": "RDimRotatedEntity",
    "radial": "RDimRadialEntity",
    "diametric": "RDimDiametricEntity",
    "angular": "RDimAngular3PEntity",
}

_PATTERNS = [
    "ANSI31",
    "ANSI32",
    "ANSI33",
    "ANSI34",
    "ANSI35",
    "ANSI36",
    "ANSI37",
    "ANSI38",
    "AR-CONC",
    "AR-HBONE",
    "AR-BRSTD",
    "SOLID",
    "EARTH",
    "GRASS",
    "GRAVEL",
    "LINE",
]


def _build_dim_script(dimensions: list[dict]) -> str:
    lines = ["var op = new RAddObjectsOperation();"]
    for i, d in enumerate(dimensions):
        dim_type = d.get("type", "aligned")
        if dim_type not in _DIM_TYPE_MAP:
            continue

        if dim_type == "aligned":
            x1, y1 = d.get("x1", 0), d.get("y1", 0)
            x2, y2 = d.get("x2", 0), d.get("y2", 0)
            xd, yd = d.get("xd", (x1 + x2) / 2), d.get("yd", y1 - 20)
            lines.append(
                f"op.addObject(new RDimAlignedEntity(document, "
                f"new RDimAlignedData(new RVector({x1},{y1}), new RVector({x2},{y2}), new RVector({xd},{yd}))));"
            )
        elif dim_type == "rotated":
            x1, y1 = d.get("x1", 0), d.get("y1", 0)
            x2, y2 = d.get("x2", 0), d.get("y2", 0)
            xd, yd = d.get("xd", (x1 + x2) / 2), d.get("yd", y1 - 20)
            angle = d.get("angle", 0)
            lines.append(
                f"op.addObject(new RDimRotatedEntity(document, "
                f"new RDimRotatedData(new RVector({x1},{y1}), new RVector({x2},{y2}), new RVector({xd},{yd}), {angle})));"
            )
        elif dim_type == "radial":
            cx, cy = d.get("cx", 0), d.get("cy", 0)
            px, py = d.get("px", cx + 10), d.get("py", cy)
            lines.append(
                f"op.addObject(new RDimRadialEntity(document, "
                f"new RDimRadialData(new RVector({cx},{cy}), new RVector({px},{py}), 0)));"
            )
        elif dim_type == "diametric":
            cx, cy = d.get("cx", 0), d.get("cy", 0)
            px, py = d.get("px", cx + 10), d.get("py", cy)
            lines.append(
                f"op.addObject(new RDimDiametricEntity(document, "
                f"new RDimDiametricData(new RVector({cx},{cy}), new RVector({px},{py}))));"
            )
        elif dim_type == "angular":
            cx, cy = d.get("cx", 0), d.get("cy", 0)
            x1, y1 = d.get("x1", cx + 100), d.get("y1", cy)
            x2, y2 = d.get("x2", cx), d.get("y2", cy + 50)
            xd, yd = d.get("xd", cx + 50), d.get("yd", cy - 30)
            lines.append(
                f"op.addObject(new RDimAngular3PEntity(document, "
                f"new RDimAngular3PData(new RVector({cx},{cy}), new RVector({x1},{y1}), new RVector({x2},{y2}), new RVector({xd},{yd}))));"
            )

    lines.append("op.apply(document);")
    return "\n".join(lines)


async def plan_dimension(
    file_name: Annotated[str, Field(description="DXF/DWG filename in the depot to add dimensions to.")],
    dimensions: Annotated[
        list[dict],
        Field(
            description="""List of dimension specifications. Each dict requires:
- type: "aligned" (linear), "rotated" (angled linear), "radial" (radius), "diametric" (diameter), "angular"
- For aligned/rotated: x1, y1, x2, y2 (extension line origins), xd, yd (dimension line position)
- For radial/diametric: cx, cy (center), px, py (point on circle)
- For angular: cx, cy (center), x1, y1 (line1 endpoint), x2, y2 (line2 endpoint), xd, yd (arc position)
- Optional: layer (default "0")
"""
        ),
    ],
    output_name: Annotated[
        str, Field(default="", description="Output filename. Default: <input>_dimensioned.dxf")
    ] = "",
) -> dict:
    """Add dimension entities to a DXF drawing using QCAD Pro.

    Adds aligned, radial, diametric, angular, or rotated dimensions to
    existing geometry. Requires QCAD Pro installed.

    ## Return Format
    {"success": bool, "output": str, "data": {"entity_count": int, "dim_count": int}}

    ## Examples
    await plan_dimension(file_name="floorplan.dxf", dimensions=[
        {"type": "aligned", "x1": 0, "y1": 0, "x2": 5000, "y2": 0, "xd": 2500, "yd": -500},
        {"type": "radial", "cx": 2500, "cy": 2000, "px": 2800, "py": 2000},
    ])
    """
    if not qcad_pro.is_installed():
        return {"success": False, "error": "QCAD Pro required. Set QCAD_PRO_PATH."}

    in_path = os.path.join(DEPOT_DIR, file_name)
    if not os.path.isfile(in_path):
        return {"success": False, "error": f"File not found: {file_name}"}

    out_name = output_name or f"{Path(file_name).stem}_dimensioned.dxf"
    out_path = os.path.join(OUTPUT_DIR, out_name)

    code = _build_dim_script(dimensions)
    result = qcad_pro.run_script(
        user_code=code,
        input_file=in_path,
        output_file=out_path,
        timeout=120,
    )

    if result.get("success"):
        result["output"] = out_name
        data = result.get("data", {})
        data["dim_count"] = len([d for d in dimensions if d.get("type") in _DIM_TYPE_MAP])
        result["data"] = data
    return result


async def plan_measure(
    file_name: Annotated[str, Field(description="DXF/DWG filename in the depot to measure.")],
) -> dict:
    """Measure distances, angles, areas, and perimeters in a DXF drawing via QCAD Pro.

    Uses QCAD Pro's geometry engine for precise measurements. Returns structured
    measurement data for all entities in the drawing.

    Requires QCAD Pro installed.

    ## Return Format
    {"success": bool, "data": {"entity_count": int, "entities": [...], "total_line_length": float, "total_area": float}}

    ## Examples
    await plan_measure(file_name="floorplan.dxf")
    """
    if not qcad_pro.is_installed():
        return {"success": False, "error": "QCAD Pro required."}

    in_path = os.path.join(DEPOT_DIR, file_name)
    if not os.path.isfile(in_path):
        return {"success": False, "error": f"File not found: {file_name}"}

    code = """var ents = document.queryAllEntities();
var measurements = [];
var totalLength = 0;
var totalArea = 0;

for (var i = 0; i < ents.length; i++) {
    var e = document.queryEntity(ents[i]);
    if (!e) continue;
    var m = {"id": ents[i].toString()};

    if (e instanceof RLineEntity) {
        var data = e.getData();
        var dx = data.getEndPoint().getX() - data.getStartPoint().getX();
        var dy = data.getEndPoint().getY() - data.getStartPoint().getY();
        var length = Math.sqrt(dx*dx + dy*dy);
        m["type"] = "line";
        m["length"] = length;
        m["angle_deg"] = Math.atan2(dy, dx) * 180 / Math.PI;
        m["x1"] = data.getStartPoint().getX();
        m["y1"] = data.getStartPoint().getY();
        m["x2"] = data.getEndPoint().getX();
        m["y2"] = data.getEndPoint().getY();
        totalLength += length;
    } else if (e instanceof RArcEntity) {
        var data = e.getData();
        m["type"] = "arc";
        m["radius"] = data.getRadius();
        m["center_x"] = data.getCenter().getX();
        m["center_y"] = data.getCenter().getY();
        m["start_angle"] = data.getStartAngle() * 180 / Math.PI;
        m["end_angle"] = data.getEndAngle() * 180 / Math.PI;
    } else if (e instanceof RCircleEntity) {
        var data = e.getData();
        var r = data.getRadius();
        m["type"] = "circle";
        m["radius"] = r;
        m["center_x"] = data.getCenter().getX();
        m["center_y"] = data.getCenter().getY();
        m["area"] = Math.PI * r * r;
        m["circumference"] = 2 * Math.PI * r;
        totalArea += m["area"];
    } else if (e instanceof RPolylineEntity) {
        var vertices = e.getData().getVertices();
        m["type"] = "polyline";
        m["vertex_count"] = vertices.length;
        var polyLength = 0;
        for (var j = 0; j < vertices.length - 1; j++) {
            var dx = vertices[j+1].getX() - vertices[j].getX();
            var dy = vertices[j+1].getY() - vertices[j].getY();
            polyLength += Math.sqrt(dx*dx + dy*dy);
        }
        var last = vertices[vertices.length - 1];
        var first = vertices[0];
        var dxClose = first.getX() - last.getX();
        var dyClose = first.getY() - last.getY();
        m["closed"] = (Math.abs(dxClose) < 0.001 && Math.abs(dyClose) < 0.001);
        m["length"] = polyLength;
        totalLength += polyLength;
    } else if (e instanceof RSplineEntity) {
        m["type"] = "spline";
    } else if (e instanceof RTextEntity) {
        var data = e.getData();
        m["type"] = "text";
        m["text"] = data.getText();
        m["height"] = data.getHeight();
    } else if (e instanceof RDimEntity) {
        m["type"] = "dimension";
    } else if (e instanceof RHatchEntity) {
        m["type"] = "hatch";
    } else if (e instanceof RBlockRefEntity) {
        m["type"] = "block_ref";
    } else {
        m["type"] = "unknown_" + e.getType();
    }

    measurements.push(m);
}

print("__QCAD_MCP_MEASURE__");
print(JSON.stringify({
    "entity_count": ents.length,
    "total_line_length": totalLength,
    "total_area": totalArea,
    "entities": measurements
}));
"""
    result = qcad_pro.exec_in_live(code, file_name=in_path, timeout=60)
    if result.get("success"):
        stdout = result.get("stdout", "")
        measure_data = parse_marker(stdout, "__QCAD_MCP_MEASURE__")
        if measure_data:
            return {"success": True, "data": measure_data}
        return {"success": True, "data": result.get("data", {}), "warning": "Measurement data not found in output"}
    return result


async def plan_text(
    file_name: Annotated[str, Field(description="DXF/DWG filename in the depot.")],
    texts: Annotated[
        list[dict],
        Field(
            description="""List of text annotations. Each dict:
- text: string content
- x, y: position
- height: text height (default 5)
- layer: layer name (default "0")
- rotation: degrees (default 0)
- halign: "left"|"center"|"right" (default "left")
- valign: "top"|"middle"|"bottom"|"baseline" (default "baseline")
- bold: bool (default false)
- italic: bool (default false)
"""
        ),
    ],
    output_name: Annotated[str, Field(default="", description="Output filename. Default: <input>_annotated.dxf")] = "",
) -> dict:
    """Add text annotations to a DXF drawing via QCAD Pro.

    Supports multi-line text with configurable height, alignment, rotation,
    and font styling (bold, italic).

    Requires QCAD Pro installed.

    ## Return Format
    {"success": bool, "output": str, "data": {"entity_count": int, "text_count": int}}

    ## Examples
    await plan_text(file_name="floorplan.dxf", texts=[
        {"text": "Living Room", "x": 2500, "y": 3000, "height": 250, "halign": "center"},
        {"text": "Kitchen", "x": 6000, "y": 2000, "height": 250, "layer": "Labels"},
    ])
    """
    if not qcad_pro.is_installed():
        return {"success": False, "error": "QCAD Pro required."}

    in_path = os.path.join(DEPOT_DIR, file_name)
    if not os.path.isfile(in_path):
        return {"success": False, "error": f"File not found: {file_name}"}

    out_name = output_name or f"{Path(file_name).stem}_annotated.dxf"
    out_path = os.path.join(OUTPUT_DIR, out_name)

    lines = ["var op = new RAddObjectsOperation();"]
    var_idx = 0
    for t in texts:
        text = t.get("text", "").replace("'", "\\'").replace("\n", "\\n")
        x, y = t.get("x", 0), t.get("y", 0)
        height = t.get("height", 5)
        rotation = t.get("rotation", 0)
        halign_map = {"left": 0, "center": 1, "right": 2}
        valign_map = {"top": 1, "middle": 2, "bottom": 3, "baseline": 0}
        ha = halign_map.get(t.get("halign", "left"), 0)
        va = valign_map.get(t.get("valign", "baseline"), 0)
        bold = "true" if t.get("bold") else "false"
        italic = "true" if t.get("italic") else "false"

        lines.append(
            f"var td_{var_idx} = new RTextData("
            f"new RVector({x},{y}), {height}, 0, '{text}', "
            f"'Standard', {ha}, {va}, RS.UnknownUnit, 0, 0, 0, "
            f"{bold}, {italic}, {rotation}, false, false);"
        )
        lines.append(f"op.addObject(new RTextEntity(document, td_{var_idx}));")
        var_idx += 1

    lines.append("op.apply(document);")
    code = "\n".join(lines)

    result = qcad_pro.run_script(
        user_code=code,
        input_file=in_path,
        output_file=out_path,
        timeout=60,
    )

    if result.get("success"):
        result["output"] = out_name
        data = result.get("data", {})
        data["text_count"] = len(texts)
        result["data"] = data
    return result


async def plan_hatch(
    file_name: Annotated[str, Field(description="DXF/DWG filename in the depot.")],
    hatches: Annotated[
        list[dict],
        Field(
            description="""List of hatch specifications. Each dict:
- points: [[x1,y1], [x2,y2], ...] closed polygon boundary (required)
- pattern: pattern name (default "ANSI31") - see list below
- scale: pattern scale (default 1.0)
- angle: pattern rotation in degrees (default 0)
- layer: layer name (default "0")
- color: color name or #RRGGBB (default layer color)

Available patterns: ANSI31-38, AR-CONC, AR-HBONE, AR-BRSTD, SOLID, EARTH, GRASS, GRAVEL, LINE
"""
        ),
    ],
    output_name: Annotated[str, Field(default="", description="Output filename. Default: <input>_hatched.dxf")] = "",
) -> dict:
    """Add hatch/fill patterns to closed regions in a DXF drawing via QCAD Pro.

    Supports ANSI, architectural, earth, and solid fill patterns with
    configurable scale and angle.

    Requires QCAD Pro installed.

    ## Return Format
    {"success": bool, "output": str, "data": {"entity_count": int, "hatch_count": int}}

    ## Examples
    await plan_hatch(file_name="floorplan.dxf", hatches=[
        {"points": [[0,0], [5000,0], [5000,4000], [0,4000]], "pattern": "AR-CONC", "scale": 0.5},
        {"points": [[1000,1000], [2000,1000], [2000,2000], [1000,2000]], "pattern": "SOLID", "color": "#FF0000"},
    ])
    """
    if not qcad_pro.is_installed():
        return {"success": False, "error": "QCAD Pro required."}

    in_path = os.path.join(DEPOT_DIR, file_name)
    if not os.path.isfile(in_path):
        return {"success": False, "error": f"File not found: {file_name}"}

    out_name = output_name or f"{Path(file_name).stem}_hatched.dxf"
    out_path = os.path.join(OUTPUT_DIR, out_name)

    lines = ["var op = new RAddObjectsOperation();"]
    for i, h in enumerate(hatches):
        pts = h.get("points", [])
        if len(pts) < 3:
            continue
        pattern = h.get("pattern", "ANSI31")
        scale = h.get("scale", 1.0)
        angle = h.get("angle", 0)
        solid = "true" if pattern.upper() == "SOLID" else "false"
        rad = angle * 3.141592653589793 / 180

        pts_js = ", ".join(f"new RVector({p[0]},{p[1]})" for p in pts)
        lines.append(f"var boundary_{i} = [{pts_js}];")
        lines.append(f"var hd_{i} = new RHatchData({solid}, {scale}, {rad}, '{pattern}', boundary_{i});")
        lines.append(f"op.addObject(new RHatchEntity(document, hd_{i}));")

    lines.append("op.apply(document);")
    code = "\n".join(lines)

    result = qcad_pro.run_script(
        user_code=code,
        input_file=in_path,
        output_file=out_path,
        timeout=60,
    )

    if result.get("success"):
        result["output"] = out_name
        data = result.get("data", {})
        data["hatch_count"] = len(hatches)
        result["data"] = data
    return result


async def plan_block_insert(
    file_name: Annotated[str, Field(description="DXF/DWG filename in the depot.")],
    inserts: Annotated[
        list[dict],
        Field(
            description="""List of block insertions. Each dict:
- block_name: name of the block to insert (must exist in the drawing or be loaded from depot)
- x, y: insertion position
- scale_x, scale_y: scale factors (default 1.0)
- rotation: rotation in degrees (default 0)
- layer: target layer (default current layer)
- columns, rows, col_spacing, row_spacing: optional array parameters
"""
        ),
    ],
    output_name: Annotated[str, Field(default="", description="Output filename. Default: <input>_blocks.dxf")] = "",
) -> dict:
    """Insert block references (doors, windows, furniture) into a DXF drawing.

    Blocks are reusable symbols stored in the drawing. Use plan_blocks to
    search/download blocks to the depot first, then insert them.

    Requires QCAD Pro.

    ## Return Format
    {"success": bool, "output": str, "data": {"entity_count": int, "insert_count": int}}

    ## Examples
    await plan_block_insert(file_name="floorplan.dxf", inserts=[
        {"block_name": "DOOR", "x": 2000, "y": 0, "rotation": 0},
        {"block_name": "WINDOW", "x": 5000, "y": 3000, "scale_x": 1.5},
    ])
    """
    if not qcad_pro.is_installed():
        return {"success": False, "error": "QCAD Pro required."}

    in_path = os.path.join(DEPOT_DIR, file_name)
    if not os.path.isfile(in_path):
        return {"success": False, "error": f"File not found: {file_name}"}

    out_name = output_name or f"{Path(file_name).stem}_blocks.dxf"
    out_path = os.path.join(OUTPUT_DIR, out_name)

    lines = ["var op = new RAddObjectsOperation();"]
    for i, ins in enumerate(inserts):
        x, y = ins.get("x", 0), ins.get("y", 0)
        sx, sy = ins.get("scale_x", 1.0), ins.get("scale_y", 1.0)
        rotation = (ins.get("rotation", 0) * 3.141592653589793) / 180
        columns = ins.get("columns", 1)
        rows = ins.get("rows", 1)
        cs = ins.get("col_spacing", 0)
        rs = ins.get("row_spacing", 0)

        for col in range(columns):
            for row in range(rows):
                px = x + col * cs
                py = y + row * rs
                lines.append(
                    f"var pt_{i}_{col}_{row} = new RVector({px}, {py});"
                    f"op.addObject(new RBlockReferenceEntity(document, null, "
                    f"new RBlockReferenceData(pt_{i}_{col}_{row}, new RVector({sx},{sy}), {rotation}, null)));"
                )

    lines.append("op.apply(document);")
    code = "\n".join(lines)

    result = qcad_pro.run_script(
        user_code=code,
        input_file=in_path,
        output_file=out_path,
        timeout=60,
    )

    if result.get("success"):
        result["output"] = out_name
        data = result.get("data", {})
        data["insert_count"] = sum(ins.get("columns", 1) * ins.get("rows", 1) for ins in inserts)
        result["data"] = data
    return result


async def plan_array(
    file_name: Annotated[str, Field(description="DXF/DWG filename in the depot.")],
    pattern: Annotated[str, Field(description="Array type: 'rectangular' or 'polar'.")],
    count: Annotated[int, Field(description="Number of copies (including the original).")],
    params: Annotated[
        dict,
        Field(
            default={},
            description="""Array parameters:
- For rectangular: dx, dy (spacing in mm)
- For polar: cx, cy (center point), angle (total angle in degrees, default 360)
""",
        ),
    ] = {},
    output_name: Annotated[str, Field(default="", description="Output filename. Default: <input>_array.dxf")] = "",
) -> dict:
    """Create a rectangular or polar array of all entities in a drawing.

    Useful for: window grids, column grids, bolt patterns, radial furniture
    arrangements, repeating architectural features.

    Requires QCAD Pro.

    ## Return Format
    {"success": bool, "output": str, "data": {"entity_count": int, "copies": int}}

    ## Examples
    await plan_array(file_name="window.dxf", pattern="rectangular", count=4, params={"dx": 1000, "dy": 800})
    await plan_array(file_name="bolt.dxf", pattern="polar", count=8, params={"cx": 50, "cy": 50, "angle": 360})
    """
    if not qcad_pro.is_installed():
        return {"success": False, "error": "QCAD Pro required."}

    in_path = os.path.join(DEPOT_DIR, file_name)
    if not os.path.isfile(in_path):
        return {"success": False, "error": f"File not found: {file_name}"}

    out_name = output_name or f"{Path(file_name).stem}_array.dxf"
    out_path = os.path.join(OUTPUT_DIR, out_name)

    if pattern == "rectangular":
        dx = params.get("dx", 1000)
        dy = params.get("dy", 800)
        code = f"""var ents = document.queryAllEntities();
var originalCount = ents.length;
var op = new RAddObjectsOperation();

for (var i = 1; i < {count}; i++) {{
    for (var j = 0; j < ents.length; j++) {{
        var e = document.queryEntity(ents[j]);
        if (!e) continue;
        var copy = e.clone();
        copy.scale(1.0, new RVector(0,0)); // ensure identity
        copy.move(new RVector(i * {dx}, i * {dy}));
        op.addObject(copy);
    }}
}}
op.apply(document);
"""
    elif pattern == "polar":
        cx = params.get("cx", 0)
        cy = params.get("cy", 0)
        total_angle = params.get("angle", 360)
        angle_step = total_angle / count
        code = f"""var ents = document.queryAllEntities();
var originalCount = ents.length;
var op = new RAddObjectsOperation();
var center = new RVector({cx}, {cy});

for (var i = 1; i < {count}; i++) {{
    var angle = (i * {angle_step}) * Math.PI / 180;
    for (var j = 0; j < ents.length; j++) {{
        var e = document.queryEntity(ents[j]);
        if (!e) continue;
        var copy = e.clone();
        copy.rotate(angle, center);
        op.addObject(copy);
    }}
}}
op.apply(document);
"""
    else:
        return {"success": False, "error": f"Unknown pattern: {pattern}. Use 'rectangular' or 'polar'."}

    result = qcad_pro.run_script(
        user_code=code,
        input_file=in_path,
        output_file=out_path,
        timeout=60,
    )

    if result.get("success"):
        result["output"] = out_name
        data = result.get("data", {})
        data["copies"] = count - 1
        result["data"] = data
    return result


async def plan_wall_data(
    file_name: Annotated[str, Field(description="DXF/DWG filename in the depot.")],
    wall_layers: Annotated[
        str,
        Field(
            default="",
            description="Comma-separated layer names containing walls. Empty = auto-detect layers with 'wall', 'mauer', or 'wand' in the name.",
        ),
    ] = "",
    wall_thickness: Annotated[
        float, Field(default=0.3, description="Default wall thickness in metres if not otherwise specified.")
    ] = 0.3,
) -> dict:
    """Extract wall segment coordinates as structured BIM-ready JSON.

    Reads a DXF floor plan and exports wall line segments as structured
    data ready for freecad-mcp BIM tools (bim_create_wall).

    Each wall segment includes: start/end coordinates, length, angle,
    and layer name. LWPOLYLINE entities on wall layers are decomposed
    into individual segments.

    Requires QCAD Pro.

    ## Return Format
    {"success": bool, "data": {"wall_count": int, "total_length_m": float, "walls": [{"x1":.., "y1":.., "x2":.., "y2":.., "length_mm":.., "angle_deg":.., "layer":..}]}}

    ## Examples
    await plan_wall_data(file_name="floorplan.dxf")
    await plan_wall_data(file_name="floorplan.dxf", wall_layers="Walls, Exterior")
    """
    if not qcad_pro.is_installed():
        return {"success": False, "error": "QCAD Pro required."}

    in_path = os.path.join(DEPOT_DIR, file_name)
    if not os.path.isfile(in_path):
        return {"success": False, "error": f"File not found: {file_name}"}

    layer_filter = wall_layers.replace("'", "\\'")

    code = f"""var ents = document.queryAllEntities();
var walls = [];
var totalLength = 0;

var filterLayers = "{layer_filter}";
var layerNames = filterLayers ? filterLayers.split(",") : [];

for (var i = 0; i < ents.length; i++) {{
    var e = document.queryEntity(ents[i]);
    if (!e) continue;

    var layer = "0";
    try {{
        var lid = e.getLayerId();
        if (lid && lid.isValid()) {{
            var l = document.queryLayer(lid);
            if (l) layer = l.getName().toLowerCase();
        }}
    }} catch (ex) {{}}

    // Apply layer filter
    if (layerNames.length > 0) {{
        var match = false;
        for (var j = 0; j < layerNames.length; j++) {{
            if (layer === layerNames[j].toLowerCase().trim()) {{ match = true; break; }}
        }}
        if (!match) continue;
    }} else {{
        // Auto-detect wall layers
        var isWallLayer = layer.indexOf("wall") >= 0 ||
                           layer.indexOf("mauer") >= 0 ||
                           layer.indexOf("wand") >= 0 ||
                           layer === "0";
        if (!isWallLayer) continue;
    }}

    if (e instanceof RLineEntity) {{
        var d = e.getData();
        var x1 = d.getStartPoint().getX();
        var y1 = d.getStartPoint().getY();
        var x2 = d.getEndPoint().getX();
        var y2 = d.getEndPoint().getY();
        var dx = x2 - x1;
        var dy = y2 - y1;
        var len = Math.sqrt(dx*dx + dy*dy);
        var ang = Math.atan2(dy, dx) * 180 / Math.PI;
        walls.push({{"type":"line","x1":x1,"y1":y1,"x2":x2,"y2":y2,"length_mm":len,"angle_deg":ang,"layer":layer}});
        totalLength += len;
    }} else if (e instanceof RPolylineEntity) {{
        var verts = e.getData().getVertices();
        for (var j = 0; j < verts.length - 1; j++) {{
            var v1 = verts[j];
            var v2 = verts[j + 1];
            var dx = v2.getX() - v1.getX();
            var dy = v2.getY() - v1.getY();
            var len = Math.sqrt(dx*dx + dy*dy);
            var ang = Math.atan2(dy, dx) * 180 / Math.PI;
            walls.push({{"type":"polyline_seg","x1":v1.getX(),"y1":v1.getY(),"x2":v2.getX(),"y2":v2.getY(),"length_mm":len,"angle_deg":ang,"layer":layer}});
            totalLength += len;
        }}
    }}
}}

print("__QCAD_MCP_MEASURE__");
print(JSON.stringify({{
    "wall_count": walls.length,
    "total_length_m": totalLength / 1000,
    "walls": walls
}}));
"""

    result = qcad_pro.exec_in_live(code, file_name=in_path, timeout=60)
    if result.get("success"):
        stdout = result.get("stdout", "")
        wall_data = qcad_pro._parse_marker(stdout, "__QCAD_MCP_MEASURE__")
        if wall_data:
            return {"success": True, "data": wall_data}
        return {"success": True, "data": result.get("data", {}), "warning": "Wall data marker not found"}
    return result


async def plan_beam_analysis(
    beams: Annotated[
        list[dict],
        Field(
            description="""List of 2D beam segments. Each dict:
- x1, y1, x2, y2: start and end coordinates (mm)
- height: beam section height in mm (default 300)
- width: beam section width in mm (default 200)
- E: elastic modulus in MPa (default 25000 = concrete, 210000 = steel)
"""
        ),
    ],
    supports: Annotated[
        list[dict],
        Field(
            default_factory=list,
            description="""List of supports. Each dict:
- node_index: beam segment index (0-based) to place support
- location: 'start' or 'end' of the segment
- dof: comma-separated restrained DOFs: 'x,y,rz' for fixed, 'x,y' for pinned, 'y' for roller
""",
        ),
    ],
    loads: Annotated[
        list[dict],
        Field(
            default_factory=list,
            description="""List of loads. Each dict:
- type: 'point' (kN) or 'distributed' (kN/m)
- beam_index: beam segment index (0-based)
- magnitude: force in kN (positive = downward for y-direction)
- For point loads: position (0 to 1, fraction along beam)
- For distributed loads: uniform over full beam length
""",
        ),
    ],
) -> dict:
    """2D beam structural analysis using direct stiffness FEM.

    Computes bending moments, shear forces, axial forces, and deflections
    for planar beam structures. Suitable for architectural wall loading
    analysis, lintel design, and simple frame structures.

    Supports: pinned/fixed/roller supports, point loads, distributed loads.
    Concrete and steel material presets.

    ## Return Format
    {"success": bool, "data": {"nodes": [...], "beams": [{"moment":[...], "shear":float, "axial":float, "max_deflection_mm":float, ...}], "reactions": [...]}}

    ## Examples
    # Simply supported concrete beam, 5m span, 10kN point load at midspan
    await plan_beam_analysis(beams=[{"x1":0,"y1":0,"x2":5000,"y2":0,"height":400,"width":200,"E":25000}], supports=[{"node_index":0,"location":"start","dof":"x,y"},{"node_index":0,"location":"end","dof":"y"}], loads=[{"type":"point","beam_index":0,"position":0.5,"magnitude":10}])
    """
    import numpy as np

    if not beams:
        return {"success": False, "error": "No beam segments provided."}

    # ─── Build node index ───────────────────────────────────────────
    # Map each beam's start/end to a global node number
    nodes = []
    node_map = {}  # (x, y) rounded to 1mm → node_index
    beam_nodes = []  # list of (start_node, end_node) per beam

    for b in beams:
        x1 = round(b.get("x1", 0))
        y1 = round(b.get("y1", 0))
        x2 = round(b.get("x2", 0))
        y2 = round(b.get("y2", 0))
        key1 = (x1, y1)
        key2 = (x2, y2)
        if key1 not in node_map:
            node_map[key1] = len(nodes)
            nodes.append({"x": x1, "y": y1})
        if key2 not in node_map:
            node_map[key2] = len(nodes)
            nodes.append({"x": x2, "y": y2})
        beam_nodes.append((node_map[key1], node_map[key2]))

    n_nodes = len(nodes)
    n_dof = n_nodes * 3  # ux, uy, rot per node

    # ─── Global stiffness matrix ─────────────────────────────────────
    K = np.zeros((n_dof, n_dof))
    F = np.zeros(n_dof)

    for i, (ni, nj) in enumerate(beam_nodes):
        b = beams[i]
        x1, y1 = b["x1"], b["y1"]
        x2, y2 = b["x2"], b["y2"]
        L = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        if L < 1e-6:
            continue
        cos_a = (x2 - x1) / L
        sin_a = (y2 - y1) / L

        h = b.get("height", 300)  # mm
        w = b.get("width", 200)  # mm
        E_val = b.get("E", 25000)  # MPa (concrete)

        A = w * h  # mm²
        inertia = w * h**3 / 12  # mm⁴
        EA = E_val * A
        EI = E_val * inertia

        # Local stiffness matrix (6x6 Euler-Bernoulli)
        k_local = np.zeros((6, 6))
        k_local[0, 0] = EA / L
        k_local[0, 3] = -EA / L
        k_local[1, 1] = 12 * EI / L**3
        k_local[1, 2] = 6 * EI / L**2
        k_local[1, 4] = -12 * EI / L**3
        k_local[1, 5] = 6 * EI / L**2
        k_local[2, 2] = 4 * EI / L
        k_local[2, 4] = -6 * EI / L**2
        k_local[2, 5] = 2 * EI / L
        k_local[3, 3] = EA / L
        k_local[4, 4] = 12 * EI / L**3
        k_local[4, 5] = -6 * EI / L**2
        k_local[5, 5] = 4 * EI / L
        # Symmetry
        for r in range(6):
            for c in range(r + 1, 6):
                k_local[c, r] = k_local[r, c]

        # Transformation matrix
        T_local = np.eye(6)
        T_local[0, 0] = cos_a
        T_local[0, 1] = sin_a
        T_local[1, 0] = -sin_a
        T_local[1, 1] = cos_a
        T_local[3, 3] = cos_a
        T_local[3, 4] = sin_a
        T_local[4, 3] = -sin_a
        T_local[4, 4] = cos_a

        k_global = T_local.T @ k_local @ T_local

        # Assemble into global K
        dof_map = [ni * 3, ni * 3 + 1, ni * 3 + 2, nj * 3, nj * 3 + 1, nj * 3 + 2]
        for r in range(6):
            for c in range(6):
                K[dof_map[r], dof_map[c]] += k_global[r, c]

    # ─── Apply loads ─────────────────────────────────────────────────
    for load in loads:
        bi = load.get("beam_index", 0)
        if bi >= len(beam_nodes):
            continue
        b = beams[bi]
        x1, y1 = b["x1"], b["y1"]
        x2, y2 = b["x2"], b["y2"]
        L = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        if L < 1e-6:
            continue
        magnitude_N = load.get("magnitude", 0) * 1000  # kN → N
        cos_a = (x2 - x1) / L
        sin_a = (y2 - y1) / L

        ni, nj = beam_nodes[bi]

        if load.get("type") == "point":
            pos = load.get("position", 0.5)
            a = pos * L
            b_load = L - a
            # Shear and moment at start and end
            V_i = magnitude_N * b_load**2 * (L + 2 * a) / L**3
            M_i = magnitude_N * a * b_load**2 / L**2
            V_j = magnitude_N * a**2 * (L + 2 * b_load) / L**3
            M_j = -magnitude_N * a**2 * b_load / L**2

            # Local force vector (ux=Fx, uy=Fy, rot=M at each node)
            F_local = np.array([0, -V_i, -M_i, 0, -V_j, M_j])

            # Transform to global
            T_local = np.eye(6)
            T_local[0, 0] = cos_a
            T_local[0, 1] = sin_a
            T_local[1, 0] = -sin_a
            T_local[1, 1] = cos_a
            T_local[3, 3] = cos_a
            T_local[3, 4] = sin_a
            T_local[4, 3] = -sin_a
            T_local[4, 4] = cos_a

            f_global = T_local.T @ F_local

        elif load.get("type") == "distributed":
            w_N_mm = magnitude_N / L  # N/mm (magnitude_N is total N over beam)
            # Fixed-end forces for uniform distributed load
            F_local = np.array([0, -w_N_mm * L / 2, -w_N_mm * L**2 / 12, 0, -w_N_mm * L / 2, w_N_mm * L**2 / 12])
            T_local = np.eye(6)
            T_local[0, 0] = cos_a
            T_local[0, 1] = sin_a
            T_local[1, 0] = -sin_a
            T_local[1, 1] = cos_a
            T_local[3, 3] = cos_a
            T_local[3, 4] = sin_a
            T_local[4, 3] = -sin_a
            T_local[4, 4] = cos_a
            f_global = T_local.T @ F_local
        else:
            continue

        dof_map = [ni * 3, ni * 3 + 1, ni * 3 + 2, nj * 3, nj * 3 + 1, nj * 3 + 2]
        for j in range(6):
            F[dof_map[j]] += f_global[j]

    # ─── Apply boundary conditions ───────────────────────────────────
    constrained = set()
    for sup in supports:
        ni = sup.get("node_index", 0)
        loc = sup.get("location", "start")
        if ni >= len(beam_nodes):
            continue
        node = beam_nodes[ni][0] if loc == "start" else beam_nodes[ni][1]
        dof_str = sup.get("dof", "x,y,rz")
        for d in dof_str.split(","):
            d = d.strip()
            if d == "x":
                constrained.add(node * 3)
            elif d == "y":
                constrained.add(node * 3 + 1)
            elif d in ("rz", "z", "rot"):
                constrained.add(node * 3 + 2)

    # Auto-detect: if no supports specified, fix first node
    if not constrained:
        constrained.add(1)  # y at node 0
        constrained.add(0)  # x at node 0

    # Apply penalties
    penalty = 1e20
    free_dofs = [i for i in range(n_dof) if i not in constrained]
    K_constrained = K[np.ix_(free_dofs, free_dofs)]
    F_constrained = F[free_dofs]

    # ─── Solve ───────────────────────────────────────────────────────
    try:
        U_free = np.linalg.solve(K_constrained, F_constrained)
    except np.linalg.LinAlgError:
        return {
            "success": False,
            "error": "Stiffness matrix is singular - check supports. At least 3 restraints needed for 2D stability.",
        }

    U = np.zeros(n_dof)
    for idx, dof in enumerate(free_dofs):
        U[dof] = U_free[idx]

    # ─── Element forces ──────────────────────────────────────────────
    beam_results = []
    for i, (ni, nj) in enumerate(beam_nodes):
        b = beams[i]
        x1, y1 = b["x1"], b["y1"]
        x2, y2 = b["x2"], b["y2"]
        L = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        if L < 1e-6:
            beam_results.append({"beam_index": i, "error": "Zero-length beam"})
            continue
        cos_a = (x2 - x1) / L
        sin_a = (y2 - y1) / L

        h = b.get("height", 300)
        w = b.get("width", 200)
        E_val = b.get("E", 25000)  # MPa

        # Apply standard beam formulas for moment/shear
        # M_max = wL²/8 (distributed) or PL/4 (centered point)
        M_max = 0.0
        V_max = 0.0
        axial = 0.0

        for load in loads:
            if load.get("beam_index", 0) != i:
                continue
            mag_N = load.get("magnitude", 0) * 1000
            ltype = load.get("type", "")
            if ltype == "point":
                pos = load.get("position", 0.5)
                a = pos * L
                b_ld = L - a
                M_max += mag_N * a * b_ld / L
                V_max += mag_N * b_ld / L
            elif ltype == "distributed":
                M_max += mag_N * L / (8 * 1000)  # w_total*L/8 in N·mm
                V_max += mag_N / 2000

        # Compute axial force from displacements
        dof_map = [ni * 3, ni * 3 + 1, ni * 3 + 2, nj * 3, nj * 3 + 1, nj * 3 + 2]
        u_local = np.zeros(6)
        T = np.eye(6)
        T[0, 0] = cos_a
        T[0, 1] = sin_a
        T[1, 0] = -sin_a
        T[1, 1] = cos_a
        T[3, 3] = cos_a
        T[3, 4] = sin_a
        T[4, 3] = -sin_a
        T[4, 4] = cos_a
        u_global = U[dof_map]
        u_local = T @ u_global
        axial = (E_val * w * h / L) * (u_local[3] - u_local[0])

        # Max deflection from displacements
        defl_i = np.sqrt(U[ni * 3 + 1] ** 2 + U[ni * 3] ** 2)
        defl_j = np.sqrt(U[nj * 3 + 1] ** 2 + U[nj * 3] ** 2)
        max_defl = max(abs(defl_i), abs(defl_j))

        # Stress
        S = h * w**2 / 6  # section modulus (mm³)
        stress_moment = abs(M_max) / S if S > 0 else 0  # MPa

        beam_results.append(
            {
                "beam_index": i,
                "length_m": round(L / 1000, 3),
                "max_moment_kNm": round(M_max / 1e6, 2),
                "max_shear_kN": round(V_max / 1000, 2),
                "axial_force_kN": round(axial / 1000, 2),
                "max_deflection_mm": round(max_defl, 2),
                "max_stress_mpa": round(stress_moment, 2),
                "material_mpa": E_val,
                "section_mm": f"{w}x{h}",
                "ok": stress_moment < E_val / 15,  # rough safety check
            }
        )

    # Reactions
    reactions = []
    for const in sorted(constrained):
        node = const // 3
        dof_local = const % 3
        label = ["Fx", "Fy", "Mz"][dof_local]
        reactions.append(
            {
                "node": node,
                "dof": label,
                "reaction_N": round(float(U[const] * penalty * 1e-20), 1),
            }
        )

    return {
        "success": True,
        "data": {
            "node_count": n_nodes,
            "beam_count": len(beams),
            "nodes": nodes,
            "beams": beam_results,
            "reactions": reactions,
        },
    }


def register(mcp):
    mcp.tool(annotations=_MUTATING, version="0.3.0")(plan_dimension)
    mcp.tool(annotations=_README_ONLY, version="0.3.0")(plan_measure)
    mcp.tool(annotations=_MUTATING, version="0.3.0")(plan_text)
    mcp.tool(annotations=_MUTATING, version="0.3.0")(plan_hatch)
    mcp.tool(annotations=_MUTATING, version="0.3.0")(plan_block_insert)
    mcp.tool(annotations=_MUTATING, version="0.3.0")(plan_array)
    mcp.tool(annotations=_README_ONLY, version="0.4.0")(plan_wall_data)
    mcp.tool(annotations=_README_ONLY, version="0.4.0")(plan_beam_analysis)
