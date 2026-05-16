"""QCAD MCP modify tools: convert formats, modify entities/layers."""

import logging
import os
from pathlib import Path
from typing import Annotated

from pydantic import Field

from qcad_mcp.config import DEPOT_DIR
from qcad_mcp.helpers import (
    _ensure_meta,
    _load_dxf,
    _qcad_pro_available,
    _qcad_pro_convert,
)

logger = logging.getLogger("qcad-mcp")

_ENTITY_TYPES_HELP = "line: {'type':'line','layer':'Walls','x1':0,'y1':0,'x2':100,'y2':100}. rect: {'type':'rect','x':0,'y':0,'w':100,'h':80,'layer':'Walls'}. circle: {'type':'circle','cx':50,'cy':50,'r':20,'layer':'Columns'}"


async def plan_convert(
    file_name: Annotated[str, Field(description="DWG or DXF filename in the depot.")],
    output_name: Annotated[str, Field(description="Output filename. Must end in .dxf or .dwg.")] = "",
) -> dict:
    """Convert a CAD file between DWG and DXF formats using QCAD Pro CLI.

    Requires QCAD Pro installed at QCAD_PRO_PATH. The converted file is saved
    to the depot and immediately available for other tools.

    ## Return Format
    {"success": bool, "filename": str, "format": str}

    ## Examples
    await plan_convert(file_name="floorplan.dwg", output_name="floorplan.dxf")
    """
    ext = Path(file_name).suffix.lower()
    out_ext = Path(output_name).suffix.lower() if output_name else ".dxf"
    if ext not in (".dxf", ".dwg") or out_ext not in (".dxf", ".dwg"):
        return {"success": False, "error": "Input and output must be .dxf or .dwg"}

    if not _qcad_pro_available():
        return {"success": False, "error": "QCAD Pro CLI required for DWG/DXF conversion. Set QCAD_PRO_PATH."}

    src = os.path.join(DEPOT_DIR, file_name)
    if not os.path.isfile(src):
        return {"success": False, "error": f"File not found: {file_name}"}

    out_name = output_name or Path(file_name).stem + out_ext
    dst = os.path.join(DEPOT_DIR, out_name)
    fmt = "DWG" if out_ext == ".dwg" else "DXF"

    if _qcad_pro_convert(src, dst, fmt):
        _ensure_meta(out_name)
        return {"success": True, "filename": out_name, "format": fmt}
    return {"success": False, "error": f"QCAD Pro conversion to {fmt} failed."}


async def plan_modify(
    file_name: Annotated[str, Field(description="DXF or DWG filename in the depot.")],
    operations: Annotated[
        list[dict],
        Field(
            description="""List of modification operations. Each operation has:
- op: "delete" (delete matching entities by layer/type),
       "offset" (offset lines/polylines by distance),
       "layer-set-color" (set layer colour),
       "layer-rename" (rename layer),
       "layer-freeze" / "layer-thaw",
       "layer-lock" / "layer-unlock",
       "merge-layers" (combine two layers: {op:"merge-layers", source:"LayerA", target:"LayerB"})
- type_filter: optional DXF type filter (e.g. "LINE", "CIRCLE", "TEXT")
- layer_filter: optional layer name filter
"""
        ),
    ],
) -> dict:
    """Modify entities and layers in a DXF/DWG file.

        Operations are applied in order. The file is saved back to the depot.

        ## Return Format
        {"success": bool, "operations": int, "summary": [str, ...]}

        ## Examples
        await plan_modify(file_name="plan.dxf", operations=[{"op": "layer-set-color", "layer_filter": "Walls", "color": 7}])

    ## Examples
        await plan_modify(file_name="plan.dxf", operations=[{"op": "delete", "type_filter": "TEXT"}])
    """
    doc, err = _load_dxf(file_name)
    if doc is None:
        return {"success": False, "error": err}

    msp = doc.modelspace()
    summary = []

    for i, op in enumerate(operations):
        op_type = op.get("op", "")
        type_filter = op.get("type_filter", "")
        layer_filter = op.get("layer_filter", "")

        # Resolve entities to act on
        if op_type in ("delete", "offset"):
            targets = list(msp)
            if type_filter:
                targets = [e for e in targets if e.dxftype() == type_filter]
            if layer_filter:
                targets = [e for e in targets if e.dxf.layer == layer_filter]

        try:
            if op_type == "delete":
                for e in targets:
                    msp.delete_entity(e)
                summary.append(f"Deleted {len(targets)} entities")

            elif op_type == "offset":
                dist = op.get("distance", 0)
                for e in targets:
                    if hasattr(e, "offset_curve"):
                        try:
                            e.offset_curve(dist)
                        except Exception as ex:
                            logger.debug("offset_curve failed for entity: %s", ex)
                summary.append(f"Offset {len(targets)} entities by {dist}")

            elif op_type == "layer-set-color":
                color = op.get("color", 7)
                for layer in doc.layers:
                    if not layer_filter or layer.dxf.name == layer_filter:
                        layer.dxf.color = color
                summary.append(f"Set colour to {color}" + (f" on layer '{layer_filter}'" if layer_filter else ""))

            elif op_type == "layer-rename":
                old = op.get("old_name", "")
                new = op.get("new_name", "")
                if old and new:
                    for layer in doc.layers:
                        if layer.dxf.name == old:
                            layer.dxf.name = new
                            summary.append(f"Renamed layer '{old}' -> '{new}'")
                else:
                    summary.append("layer-rename requires old_name and new_name")

            elif op_type in ("layer-freeze", "layer-thaw"):
                freeze = op_type == "layer-freeze"
                for layer in doc.layers:
                    if not layer_filter or layer.dxf.name == layer_filter:
                        try:
                            if hasattr(layer, "is_frozen"):
                                layer.is_frozen = freeze
                        except Exception as ex:
                            logger.debug("layer freeze/thaw failed for %s: %s", layer_filter, ex)
                summary.append(f"{'Froze' if freeze else 'Thawed'} layer '{layer_filter or 'all'}'")

            elif op_type == "layer-lock" or op_type == "layer-unlock":
                lock = op_type == "layer-lock"
                for layer in doc.layers:
                    if not layer_filter or layer.dxf.name == layer_filter:
                        try:
                            if hasattr(layer, "is_locked"):
                                layer.is_locked = lock
                        except Exception as ex:
                            logger.debug("layer lock/unlock failed for %s: %s", layer_filter, ex)
                summary.append(f"{'Locked' if lock else 'Unlocked'} layer '{layer_filter or 'all'}'")

            elif op_type == "merge-layers":
                src = op.get("source", "")
                tgt = op.get("target", "")
                if src and tgt:
                    for e in list(msp):
                        if e.dxf.layer == src:
                            e.dxf.layer = tgt
                    try:
                        doc.layers.remove(src)
                    except Exception as ex:
                        logger.debug("layer remove failed for %s: %s", src, ex)
                    summary.append(f"Merged layer '{src}' -> '{tgt}'")
                else:
                    summary.append("merge-layers requires source and target")

            else:
                summary.append(f"Unknown operation: {op_type}")

        except Exception as e:
            summary.append(f"Operation {i} ({op_type}) failed: {e}")

    # Save back
    try:
        doc.saveas(os.path.join(DEPOT_DIR, file_name))
        return {"success": True, "operations": len(operations), "summary": summary}
    except Exception as e:
        return {"success": False, "error": f"Failed to save: {e}"}


def register(mcp):
    mcp.tool(version="0.3.0")(plan_convert)
    mcp.tool(version="0.3.0")(plan_modify)
