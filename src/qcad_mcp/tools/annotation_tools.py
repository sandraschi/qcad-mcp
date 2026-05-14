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
from qcad_mcp.services.qcad_pro import _parse_marker

_READ_ONLY = {"readonly": True}

_DIM_TYPE_MAP = {
    "aligned": "RDimAlignedEntity",
    "rotated": "RDimRotatedEntity",
    "radial": "RDimRadialEntity",
    "diametric": "RDimDiametricEntity",
    "angular": "RDimAngular3PEntity",
}

_PATTERNS = ["ANSI31", "ANSI32", "ANSI33", "ANSI34", "ANSI35", "ANSI36",
             "ANSI37", "ANSI38", "AR-CONC", "AR-HBONE", "AR-BRSTD",
             "SOLID", "EARTH", "GRASS", "GRAVEL", "LINE"]


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
    dimensions: Annotated[list[dict], Field(description="""List of dimension specifications. Each dict requires:
- type: "aligned" (linear), "rotated" (angled linear), "radial" (radius), "diametric" (diameter), "angular"
- For aligned/rotated: x1, y1, x2, y2 (extension line origins), xd, yd (dimension line position)
- For radial/diametric: cx, cy (center), px, py (point on circle)
- For angular: cx, cy (center), x1, y1 (line1 endpoint), x2, y2 (line2 endpoint), xd, yd (arc position)
- Optional: layer (default "0")
""")],
    output_name: Annotated[str, Field(default="", description="Output filename. Default: <input>_dimensioned.dxf")] = "",
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
        measure_data = _parse_marker(stdout, "__QCAD_MCP_MEASURE__")
        if measure_data:
            return {"success": True, "data": measure_data}
        return {"success": True, "data": result.get("data", {}), "warning": "Measurement data not found in output"}
    return result


async def plan_text(
    file_name: Annotated[str, Field(description="DXF/DWG filename in the depot.")],
    texts: Annotated[list[dict], Field(description="""List of text annotations. Each dict:
- text: string content
- x, y: position
- height: text height (default 5)
- layer: layer name (default "0")
- rotation: degrees (default 0)
- halign: "left"|"center"|"right" (default "left")
- valign: "top"|"middle"|"bottom"|"baseline" (default "baseline")
- bold: bool (default false)
- italic: bool (default false)
""")],
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

        lines.append(f"var td_{var_idx} = new RTextData("
                     f"new RVector({x},{y}), {height}, 0, '{text}', "
                     f"'Standard', {ha}, {va}, RS.UnknownUnit, 0, 0, 0, "
                     f"{bold}, {italic}, {rotation}, false, false);")
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
    hatches: Annotated[list[dict], Field(description="""List of hatch specifications. Each dict:
- points: [[x1,y1], [x2,y2], ...] closed polygon boundary (required)
- pattern: pattern name (default "ANSI31") — see list below
- scale: pattern scale (default 1.0)
- angle: pattern rotation in degrees (default 0)
- layer: layer name (default "0")
- color: color name or #RRGGBB (default layer color)

Available patterns: ANSI31-38, AR-CONC, AR-HBONE, AR-BRSTD, SOLID, EARTH, GRASS, GRAVEL, LINE
""")],
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
    inserts: Annotated[list[dict], Field(description="""List of block insertions. Each dict:
- block_name: name of the block to insert (must exist in the drawing or be loaded from depot)
- x, y: insertion position
- scale_x, scale_y: scale factors (default 1.0)
- rotation: rotation in degrees (default 0)
- layer: target layer (default current layer)
- columns, rows, col_spacing, row_spacing: optional array parameters
""")],
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
    params: Annotated[dict, Field(default_factory=dict, description="""Array parameters:
- For rectangular: dx, dy (spacing in mm)
- For polar: cx, cy (center point), angle (total angle in degrees, default 360)
""")] = {},
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


def register(mcp):
    mcp.tool()(plan_dimension)
    mcp.tool(annotations=_READ_ONLY)(plan_measure)
    mcp.tool()(plan_text)
    mcp.tool()(plan_hatch)
    mcp.tool()(plan_block_insert)
    mcp.tool()(plan_array)
