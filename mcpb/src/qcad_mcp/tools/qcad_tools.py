"""QCAD Pro tools - status check, script execution, rendering, and lightweight exec."""

import logging
import os
from pathlib import Path
from typing import Annotated

from pydantic import Field

from qcad_mcp.config import DEPOT_DIR, OUTPUT_DIR
from qcad_mcp.services import qcad_pro

logger = logging.getLogger("qcad-mcp")

_README_ONLY = {"readonly": True}

_MUTATING = {}


async def qcad_status() -> dict:
    """Check QCAD Pro installation status, version, and capabilities.

    Reports whether QCAD Pro is installed, running, and the version string.
    Use this first to determine which QCAD Pro tools are available.

    ## Return Format
    {"success": bool, "data": {"installed": bool, "running": bool, "version": str, "install_dir": str}}

    ## Examples
    await qcad_status()
    """
    return {
        "success": True,
        "data": {
            "installed": qcad_pro.is_installed(),
            "running": qcad_pro.is_running(),
            "version": qcad_pro.get_version(),
            "install_dir": str(qcad_pro._qcad_base_dir()),
        },
    }


async def plan_script(
    code: Annotated[
        str,
        Field(
            description="ECMAScript code to execute in QCAD Pro. Variables `document` and `di` (document interface) are pre-bound. Use the full QCAD API: RAddObjectsOperation, RLineEntity, RCircleEntity, RLayer, etc."
        ),
    ],
    file_name: Annotated[
        str, Field(default="", description="Optional DXF/DWG filename in depot to load before executing code.")
    ] = "",
    output_name: Annotated[
        str, Field(default="script_output.dxf", description="Output filename saved to output dir. Empty = no export.")
    ] = "script_output.dxf",
) -> dict:
    """Execute arbitrary ECMAScript in QCAD Pro against a DXF document.

    This is the most powerful tool - it provides full access to QCAD Pro's
    ECMAScript API including entity creation, modification, layer management,
    block operations, and geometry queries.

    User code has access to:
      - `document` - RDocument (the drawing)
      - `di` - RDocumentInterface (import/export)
      - Full QCAD API: RLineEntity, RCircleEntity, RArcEntity, RVector, RAddObjectsOperation, RModifyObjectsOperation, RLayer, etc.
      - Full Qt API for data processing
      - `print()` outputs are captured but only the structured result is returned

    Requires QCAD Pro installed and reachable.

    ## Return Format
    {"success": bool, "data": {"entity_count": int, "layer_count": int, "layers": [...], "errors": [...], "output_file": str}}

    ## Examples
    await plan_script(code="var op = new RAddObjectsOperation(); op.addObject(new RCircleEntity(document, new RCircleData(new RVector(50,50), 25))); op.apply(document);", output_name="circle.dxf")
    await plan_script(code="document.queryAllEntities().length;", file_name="floorplan.dxf")
    """
    if not qcad_pro.is_installed():
        return {"success": False, "error": "QCAD Pro not installed. Set QCAD_PRO_PATH env var."}

    input_path = None
    if file_name:
        input_path = os.path.join(DEPOT_DIR, file_name)
        if not os.path.isfile(input_path):
            return {"success": False, "error": f"File not found in depot: {file_name}"}

    output_path = None
    if output_name:
        output_path = os.path.join(OUTPUT_DIR, output_name)

    result = qcad_pro.run_script(
        user_code=code,
        input_file=input_path,
        output_file=output_path,
        timeout=120,
    )

    return result


async def plan_render(
    file_name: Annotated[str, Field(description="DXF/DWG filename in the depot to render.")],
    format: Annotated[str, Field(default="svg", description="Output format: svg, pdf, or bmp.")] = "svg",
    output_name: Annotated[
        str, Field(default="", description="Output filename. Auto-generated from input name if empty.")
    ] = "",
) -> dict:
    """High-fidelity rendering of a DXF/DWG via QCAD Pro.

    Uses QCAD Pro's native rendering engine for perfect output with hatches,
    TrueType fonts, dimension styles, and lineweights - superior to the
    ezdxf+matplotlib fallback used by plan_export.

    Requires QCAD Pro installed.

    ## Return Format
    {"success": bool, "output": str, "data": {"size_kb": float}}

    ## Examples
    await plan_render(file_name="floorplan.dxf", format="svg")
    await plan_render(file_name="floorplan.dxf", format="pdf", output_name="floorplan_pro.pdf")
    """
    if not qcad_pro.is_installed():
        return {"success": False, "error": "QCAD Pro not installed. Set QCAD_PRO_PATH."}

    if format not in ("svg", "pdf", "bmp"):
        return {"success": False, "error": f"Unknown format: {format}. Use svg, pdf, or bmp."}

    ext_map = {"svg": ".svg", "pdf": ".pdf", "bmp": ".bmp"}
    out_name = output_name or f"{Path(file_name).stem}{ext_map[format]}"
    out_path = os.path.join(OUTPUT_DIR, out_name)
    in_path = os.path.join(DEPOT_DIR, file_name)

    if not os.path.isfile(in_path):
        return {"success": False, "error": f"File not found in depot: {file_name}"}

    result = qcad_pro.render(
        input_path=in_path,
        output_path=out_path,
        fmt=format,
    )

    if result.get("success"):
        result["output"] = out_name
    return result


async def plan_exec(
    code: Annotated[
        str,
        Field(
            description="ECMAScript snippet to execute. Has access to `document` and `di`. Use for quick operations: queries, adding entities, modifying layers."
        ),
    ],
    file_name: Annotated[str, Field(default="", description="Optional depot filename to load before execution.")] = "",
) -> dict:
    """Execute ECMAScript in a temporary QCAD Pro session and return results.

    Quick code runner - shorter startup than plan_script since no output
    file is saved. Use for queries, lightweight modifications, or prototyping
    before committing with plan_script.

    ## Return Format
    {"success": bool, "data": {"entity_count": int, "layers": [...], "errors": [...]}}

    ## Examples
    await plan_exec(code='var op = new RAddObjectsOperation(); op.addObject(new RCircleEntity(document, new RCircleData(new RVector(10,10), 5))); op.apply(document);')
    await plan_exec(code='document.queryAllEntities().length;', file_name="floorplan.dxf")
    """
    if not qcad_pro.is_installed():
        return {"success": False, "error": "QCAD Pro not installed."}

    input_path = None
    if file_name:
        input_path = os.path.join(DEPOT_DIR, file_name)
        if not os.path.isfile(input_path):
            return {"success": False, "error": f"File not found: {file_name}"}

    return qcad_pro.exec_in_live(code, file_name=input_path or "")


def register(mcp):
    mcp.tool(annotations=_README_ONLY, version="0.3.0")(qcad_status)
    mcp.tool(annotations=_MUTATING, version="0.3.0")(plan_script)
    mcp.tool(annotations=_MUTATING, version="0.3.0")(plan_render)
    mcp.tool(annotations=_MUTATING, version="0.3.0")(plan_exec)
