"""BIM and architectural elevation tools for QCAD MCP.

Provides automated dimensioning, multi-floor building level management,
and IFC BIM schema JSON generation for cross-repo CAD/BIM pipelines.
"""

import json
import logging
import os
from pathlib import Path
from typing import Annotated

from pydantic import Field

from qcad_mcp.config import OUTPUT_DIR
from qcad_mcp.helpers import _load_dxf

logger = logging.getLogger("qcad-mcp")

_READ_ONLY = {"readonly": True}
_MUTATING = {}


async def plan_auto_dimension(
    file_name: Annotated[str, Field(description="DXF filename in depot (e.g. 'simple_floorplan.dxf').")],
    wall_layers: Annotated[
        list[str] | None, Field(default=None, description="Layer names containing wall geometry.")
    ] = None,
    offset: Annotated[float, Field(default=500.0, description="Offset distance for dimension line placement.")] = 500.0,
    output_name: Annotated[str | None, Field(default=None, description="Optional output DXF filename.")] = None,
) -> dict:
    """Automatically detect wall boundaries and insert exterior linear dimensions.

    ## Return Format
    Dictionary with `success`, `message`, and `data` containing dimension count & file path.

    ## Examples
    await plan_auto_dimension("simple_floorplan.dxf", offset=300.0)
    """
    doc, err = _load_dxf(file_name)
    if doc is None:
        return {"success": False, "error": err}

    msp = doc.modelspace()
    target_layers = [lyr.upper() for lyr in wall_layers] if wall_layers else None

    # Collect bounding points from walls
    pts = []
    for entity in msp:
        if target_layers and entity.dxf.layer.upper() not in target_layers:
            continue
        dxftype = entity.dxftype()
        if dxftype == "LINE":
            pts.append((entity.dxf.start.x, entity.dxf.start.y))
            pts.append((entity.dxf.end.x, entity.dxf.end.y))
        elif dxftype in ("LWPOLYLINE", "POLYLINE"):
            try:
                for p in entity.get_points():
                    pts.append((p[0], p[1]))
            except Exception:
                pass

    if not pts:
        return {"success": False, "error": "No wall geometry found to dimension"}

    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    # Add DIMENSIONS layer if missing
    if "DIMENSIONS" not in doc.layers:
        doc.layers.add("DIMENSIONS", color=1)

    # Insert exterior dimensions
    dim_count = 0

    # Bottom exterior horizontal dimension
    msp.add_aligned_dim(
        p1=(min_x, min_y),
        p2=(max_x, min_y),
        distance=-offset,
        dxfattribs={"layer": "DIMENSIONS"},
    )
    dim_count += 1

    # Top exterior horizontal dimension
    msp.add_aligned_dim(
        p1=(min_x, max_y),
        p2=(max_x, max_y),
        distance=offset,
        dxfattribs={"layer": "DIMENSIONS"},
    )
    dim_count += 1

    # Left exterior vertical dimension
    msp.add_aligned_dim(
        p1=(min_x, min_y),
        p2=(min_x, max_y),
        distance=offset,
        dxfattribs={"layer": "DIMENSIONS"},
    )
    dim_count += 1

    # Right exterior vertical dimension
    msp.add_aligned_dim(
        p1=(max_x, min_y),
        p2=(max_x, max_y),
        distance=-offset,
        dxfattribs={"layer": "DIMENSIONS"},
    )
    dim_count += 1

    out_fn = output_name or f"autodim_{Path(file_name).name}"
    out_path = os.path.join(OUTPUT_DIR, out_fn)
    doc.saveas(out_path)

    return {
        "success": True,
        "message": f"Added {dim_count} automated dimensions to '{out_fn}'",
        "data": {
            "dimension_count": dim_count,
            "bounds": {"min_x": min_x, "max_x": max_x, "min_y": min_y, "max_y": max_y},
            "output_name": out_fn,
            "output_path": out_path,
        },
    }


async def plan_building_meta(
    file_name: Annotated[str, Field(description="DXF filename in depot.")],
    level_name: Annotated[str | None, Field(default=None, description="Optional level filter name.")] = None,
    elevation: Annotated[float | None, Field(default=None, description="Optional base elevation.")] = None,
) -> dict:
    """Analyze multi-floor level organization and storey metadata.

    ## Return Format
    Dictionary with `success` and `data` listing detected storeys and layer mappings.

    ## Examples
    await plan_building_meta("office_layout.dxf")
    """
    doc, err = _load_dxf(file_name)
    if doc is None:
        return {"success": False, "error": err}

    layers = [layer.dxf.name for layer in doc.layers]
    storeys_map: dict[str, list[str]] = {}

    # Heuristic matching for levels/storeys
    known_prefixes = ["L0", "L1", "L2", "GROUND", "FIRST", "SECOND", "BASEMENT", "ROOF"]
    for lyr in layers:
        prefix = "DEFAULT"
        upper = lyr.upper()
        for kp in known_prefixes:
            if kp in upper:
                prefix = kp
                break
        storeys_map.setdefault(prefix, []).append(lyr)

    storeys = []
    base_elev = elevation if elevation is not None else 0.0
    floor_height = 3000.0

    for idx, (s_name, s_layers) in enumerate(storeys_map.items()):
        storeys.append(
            {
                "storey_id": f"STOREY_{idx}",
                "name": level_name if (level_name and idx == 0) else s_name,
                "elevation": base_elev + (idx * floor_height),
                "height": floor_height,
                "layer_count": len(s_layers),
                "layers": s_layers,
            }
        )

    return {
        "success": True,
        "message": f"Identified {len(storeys)} building storeys in '{file_name}'",
        "data": {
            "file_name": file_name,
            "total_storeys": len(storeys),
            "storeys": storeys,
        },
    }


async def plan_to_ifc_data(
    file_name: Annotated[str, Field(description="DXF filename in depot.")],
    wall_layers: Annotated[list[str] | None, Field(default=None, description="Wall layer names.")] = None,
    wall_height: Annotated[float, Field(default=3000.0, description="Default wall extrusion height in mm.")] = 3000.0,
    wall_thickness: Annotated[
        float, Field(default=200.0, description="Default wall thickness in mm.")
    ] = 200.0,
) -> dict:
    """Extract wall lines, doors, and windows as a structured BIM schema JSON.

    Ready for consumption by `freecad-mcp` or direct IFC compilation.

    ## Return Format
    Dictionary with `success` and `data` containing BIM schema JSON details.

    ## Examples
    await plan_to_ifc_data("simple_floorplan.dxf", wall_height=3000.0)
    """
    doc, err = _load_dxf(file_name)
    if doc is None:
        return {"success": False, "error": err}

    msp = doc.modelspace()
    target_layers = [lyr.upper() for lyr in wall_layers] if wall_layers else ["WALLS", "WALL", "0"]

    walls = []
    openings = []

    for entity in msp:
        layer_upper = entity.dxf.layer.upper()
        dxftype = entity.dxftype()

        if dxftype == "LINE" and (not target_layers or any(tl in layer_upper for tl in target_layers)):
            start = entity.dxf.start
            end = entity.dxf.end
            walls.append(
                {
                    "id": f"WALL_{len(walls)+1}",
                    "start": [start.x, start.y, 0.0],
                    "end": [end.x, end.y, 0.0],
                    "height": wall_height,
                    "thickness": wall_thickness,
                    "layer": entity.dxf.layer,
                }
            )
        elif dxftype in ("INSERT", "CIRCLE", "ARC") and any(k in layer_upper for k in ("DOOR", "WINDOW", "OPENING")):
            pos = getattr(entity.dxf, "insert", getattr(entity.dxf, "center", None))
            if pos:
                openings.append(
                    {
                        "id": f"OPENING_{len(openings)+1}",
                        "type": "DOOR" if "DOOR" in layer_upper else "WINDOW",
                        "position": [pos.x, pos.y, 0.0],
                        "layer": entity.dxf.layer,
                    }
                )

    bim_schema = {
        "project_name": Path(file_name).stem,
        "units": "mm",
        "building": {
            "name": "Building_1",
            "storeys": [
                {
                    "name": "Level_0",
                    "elevation": 0.0,
                    "height": wall_height,
                    "elements": {
                        "walls": walls,
                        "openings": openings,
                    },
                }
            ],
        },
    }

    out_json_fn = f"{Path(file_name).stem}_bim.json"
    out_json_path = os.path.join(OUTPUT_DIR, out_json_fn)
    with open(out_json_path, "w") as f:
        json.dump(bim_schema, f, indent=2)

    return {
        "success": True,
        "message": f"Extracted {len(walls)} walls and {len(openings)} openings into BIM JSON",
        "data": {
            "wall_count": len(walls),
            "opening_count": len(openings),
            "ifc_json_name": out_json_fn,
            "ifc_json_path": out_json_path,
            "bim_schema": bim_schema,
        },
    }


def register(mcp):
    mcp.tool(annotations=_MUTATING, version="0.3.0")(plan_auto_dimension)
    mcp.tool(annotations=_READ_ONLY, version="0.3.0")(plan_building_meta)
    mcp.tool(annotations=_READ_ONLY, version="0.3.0")(plan_to_ifc_data)
