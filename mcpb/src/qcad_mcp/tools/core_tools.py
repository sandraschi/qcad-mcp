"""QCAD MCP core tools: info, SVG, extrude, export, analyse, create, depot."""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Annotated

from pydantic import Field

from qcad_mcp.config import DEPOT_DIR, OUTPUT_DIR
from qcad_mcp.helpers import (
    _depot_list,
    _doc_to_info,
    _load_dxf,
    _write_meta,
)

logger = logging.getLogger("qcad-mcp")

_README_ONLY = {"readonly": True}

_MUTATING = {}


async def plan_info(
    file_name: Annotated[str, Field(description="DXF filename in the depot, e.g. floorplan.dxf")],
) -> dict:
    """
    Read a DXF file from the depot and return metadata: layers, entity counts, bounding box, blocks.

    Upload DXF files first via POST /api/v1/upload or use plan_create to generate one.

    ## Return Format
    {"success": bool, "data": {"layers": [...], "entity_counts": {...}, "bounding_box": {...}, "block_count": int}}

    ## Examples
    await plan_info(file_name="floorplan.dxf")
    """
    doc, err = _load_dxf(file_name)
    if doc is None:
        return {"success": False, "error": err}
    try:
        return {"success": True, "data": _doc_to_info(doc)}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def plan_to_svg(
    file_name: Annotated[str, Field(description="DXF filename in the depot.")],
    output_name: Annotated[str, Field(default="output.svg", description="Desired output SVG filename.")] = "output.svg",
    layers: Annotated[
        list[str] | None,
        Field(default=None, description="Optional list of layer names to include. All layers if omitted."),
    ] = None,
    background: Annotated[
        str, Field(default="white", description="Background colour: white, black, or hex (e.g. #1a1a1a).")
    ] = "white",
) -> dict:
    """
    Convert a DXF file to an SVG preview image.

    Uses ezdxf's matplotlib backend for rendering. The SVG is saved to the outputs
    directory and viewable at GET /api/v1/download/{output_name}.

    ## Return Format
    {"success": bool, "output": str, "data": {"size_kb": float}}

    ## Examples
    await plan_to_svg(file_name="floorplan.dxf")
    """
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

    doc, err = _load_dxf(file_name)
    if doc is None:
        return {"success": False, "error": err}

    svg_path = os.path.join(OUTPUT_DIR, output_name)

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        msp = doc.modelspace()

        if layers:
            entities = [e for e in msp if e.dxftype() != "VERTEX" and e.get_dxf_attrib("layer", "") in layers]
            ctx = RenderContext(doc)
            fig = plt.figure()
            ax = fig.add_subplot(111)
            out = MatplotlibBackend(ax)
            frontend = Frontend(ctx, out)
            frontend.draw_entities(entities if entities else list(msp))
            fig.savefig(svg_path, format="svg", facecolor=background)
            plt.close(fig)
        else:
            ctx = RenderContext(doc)
            fig = plt.figure()
            ax = fig.add_subplot(111)
            out = MatplotlibBackend(ax)
            frontend = Frontend(ctx, out)
            frontend.draw_layout(msp, finalize=True)
            fig.savefig(svg_path, format="svg", facecolor=background)
            plt.close(fig)

        return {"success": True, "output": output_name, "data": {"size_kb": round(os.path.getsize(svg_path) / 1024, 1)}}
    except Exception as e:
        return {"success": False, "error": f"SVG rendering failed: {e}"}


async def plan_extrude(
    file_name: Annotated[str, Field(description="DXF filename in the depot.")],
    output_name: Annotated[
        str, Field(default="extruded.stl", description="Desired output STL filename.")
    ] = "extruded.stl",
    wall_height: Annotated[
        float, Field(default=3.0, description="Wall extrusion height in metres (default 3.0m).")
    ] = 3.0,
    wall_thickness: Annotated[float, Field(default=0.3, description="Wall thickness in metres (default 0.3m).")] = 0.3,
    wall_layers: Annotated[
        list[str] | None,
        Field(
            default=None,
            description="Layer names to treat as walls. Auto-detected if omitted (matches 'wall', 'mauer', 'wand').",
        ),
    ] = None,
) -> dict:
    """
    Extrude walls from a DXF floor plan into a 3D STL mesh.

    Finds LINE and LWPOLYLINE entities on wall layers, extrudes them vertically
    to wall_height with wall_thickness on each side.

    ## Return Format
    {"success": bool, "output": str, "data": {"vertices": int, "faces": int, "wall_count": int, "size_kb": float}}

    ## Examples
    await plan_extrude(file_name="floorplan.dxf")
    await plan_extrude(file_name="floorplan.dxf", wall_height=2.5, wall_thickness=0.2)
    """
    import numpy as np
    from stl.mesh import Mesh

    doc, err = _load_dxf(file_name)
    if doc is None:
        return {"success": False, "error": err}

    stl_path = os.path.join(OUTPUT_DIR, output_name)

    try:
        msp = doc.modelspace()
        wall_keywords = ["wall", "mauer", "wand", "mur", "parete", "pared"]
        if wall_layers is None:
            all_layers = {layer.dxf.name.lower() for layer in doc.layers}
            wall_layers = [name for name in all_layers if any(kw in name for kw in wall_keywords)]
            if not wall_layers:
                wall_layers = [layer.dxf.name for layer in doc.layers]

        wall_segments = []
        for e in msp:
            layer_name = e.get_dxf_attrib("layer", "")
            if wall_layers and layer_name not in wall_layers:
                continue
            if e.dxftype() == "LINE":
                wall_segments.append(
                    {"type": "line", "start": (e.dxf.start.x, e.dxf.start.y), "end": (e.dxf.end.x, e.dxf.end.y)}
                )
            elif e.dxftype() == "LWPOLYLINE":
                pts = [(p[0], p[1]) for p in e.get_points("xy")]
                for i in range(len(pts) - 1):
                    wall_segments.append({"type": "line", "start": pts[i], "end": pts[i + 1]})
                if e.closed and len(pts) > 2:
                    wall_segments.append({"type": "line", "start": pts[-1], "end": pts[0]})
            elif e.dxftype() == "POLYLINE":
                pts = [(p[0], p[1]) for p in e.points()]
                for i in range(len(pts) - 1):
                    wall_segments.append({"type": "line", "start": pts[i], "end": pts[i + 1]})

        if not wall_segments:
            return {
                "success": False,
                "error": "No wall entities found. Try specifying wall_layers or use a DXF with LINE/LWPOLYLINE entities.",
            }

        meshes = []
        for seg in wall_segments:
            x1, y1 = seg["start"]
            x2, y2 = seg["end"]
            dx, dy = x2 - x1, y2 - y1
            length = np.sqrt(dx * dx + dy * dy)
            if length < 1e-6:
                continue
            nx, ny = -dy / length, dx / length
            hw = wall_thickness / 2.0
            v = np.array(
                [
                    [x1 - nx * hw, y1 - ny * hw, 0],
                    [x1 + nx * hw, y1 + ny * hw, 0],
                    [x2 + nx * hw, y2 + ny * hw, 0],
                    [x2 - nx * hw, y2 - ny * hw, 0],
                    [x1 - nx * hw, y1 - ny * hw, wall_height],
                    [x1 + nx * hw, y1 + ny * hw, wall_height],
                    [x2 + nx * hw, y2 + ny * hw, wall_height],
                    [x2 - nx * hw, y2 - ny * hw, wall_height],
                ]
            )
            triangles = np.array(
                [
                    [v[0], v[1], v[2]],
                    [v[0], v[2], v[3]],
                    [v[4], v[6], v[5]],
                    [v[4], v[7], v[6]],
                    [v[0], v[3], v[7]],
                    [v[0], v[7], v[4]],
                    [v[1], v[5], v[6]],
                    [v[1], v[6], v[2]],
                    [v[0], v[4], v[5]],
                    [v[0], v[5], v[1]],
                    [v[3], v[2], v[6]],
                    [v[3], v[6], v[7]],
                ]
            )
            for tri in triangles:
                mesh_data = np.zeros(1, dtype=Mesh.dtype)
                mesh_data["vectors"][0] = tri
                meshes.append(Mesh(mesh_data))

        combined = Mesh(np.concatenate([m.data for m in meshes]))
        combined.save(stl_path)

        return {
            "success": True,
            "output": output_name,
            "data": {
                "vertices": len(combined.points),
                "faces": len(combined.data),
                "wall_count": len(wall_segments),
                "size_kb": round(os.path.getsize(stl_path) / 1024, 1),
                "wall_height_m": wall_height,
                "wall_thickness_m": wall_thickness,
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def plan_export(
    file_name: Annotated[str, Field(description="DXF filename in the depot.")],
    format: Annotated[str, Field(default="svg", description="Output format: svg, pdf, or png.")] = "svg",
    output_name: Annotated[str, Field(default="", description="Output filename. Auto-generated if empty.")] = "",
) -> dict:
    """
    Export a DXF file to SVG, PDF, or PNG.

    Tries QCAD Pro for high-fidelity output first (SVG, PDF). Falls back
    to ezdxf+matplotlib if QCAD Pro is unavailable.

    For guaranteed QCAD Pro rendering, use plan_render instead.

    ## Return Format
    {"success": bool, "output": str, "data": {"size_kb": float, "backend": str}}

    ## Examples
    await plan_export(file_name="floorplan.dxf", format="svg")
    """
    from qcad_mcp.services import qcad_pro

    ext_map = {"svg": ".svg", "pdf": ".pdf", "png": ".png"}
    if format not in ext_map:
        return {"success": False, "error": f"Unknown format: {format}. Use svg, pdf, or png."}

    out_name = output_name or f"{Path(file_name).stem}{ext_map[format]}"
    out_path = os.path.join(OUTPUT_DIR, out_name)
    in_path = os.path.join(DEPOT_DIR, file_name)

    if not os.path.isfile(in_path):
        return {"success": False, "error": f"File not found in depot: {file_name}"}

    # Try QCAD Pro for SVG/PDF (superior rendering)
    if qcad_pro.is_installed() and format in ("svg", "pdf"):
        fmt_pro = format if format != "png" else "bmp"
        render_result = qcad_pro.render(in_path, out_path, fmt_pro)
        if render_result.get("success"):
            return {
                "success": True,
                "output": out_name,
                "data": {"size_kb": render_result["size_kb"], "backend": "qcad_pro"},
            }

    # For PNG, try QCAD Pro BMP then convert via Pillow
    if qcad_pro.is_installed() and format == "png":
        bmp_path = out_path.replace(".png", "_temp.bmp")
        bmp_result = qcad_pro.render(in_path, bmp_path, "bmp")
        if bmp_result.get("success"):
            try:
                from PIL import Image

                Image.open(bmp_path).save(out_path, "PNG")
                os.unlink(bmp_path)
                return {
                    "success": True,
                    "output": out_name,
                    "data": {"size_kb": round(os.path.getsize(out_path) / 1024, 1), "backend": "qcad_pro"},
                }
            except Exception:
                if os.path.isfile(bmp_path):
                    os.unlink(bmp_path)

    # Fallback to ezdxf+matplotlib
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

    doc, err = _load_dxf(file_name)
    if doc is None:
        return {"success": False, "error": err}

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        ctx = RenderContext(doc)
        fig = plt.figure(figsize=(20, 15))
        ax = fig.add_subplot(111)
        out = MatplotlibBackend(ax)
        frontend = Frontend(ctx, out)
        frontend.draw_layout(doc.modelspace(), finalize=True)
        fig.savefig(out_path, format=format, facecolor="white", dpi=150)
        plt.close(fig)

        return {
            "success": True,
            "output": out_name,
            "data": {"size_kb": round(os.path.getsize(out_path) / 1024, 1), "backend": "ezdxf+matplotlib"},
        }
    except Exception as e:
        return {"success": False, "error": f"Export failed: {e}"}


async def plan_analyse(
    file_name: Annotated[str, Field(description="DXF filename in the depot.")],
) -> dict:
    """
    Analyse a DXF floor plan: detect rooms, calculate areas, identify doors/windows.

    ## Return Format
    {"success": bool, "data": {"rooms": [...], "doors_windows": [...], "wall_length_m": float}}

    ## Examples
    await plan_analyse(file_name="floorplan.dxf")
    """
    import numpy as np
    from ezdxf.math import area

    doc, err = _load_dxf(file_name)
    if doc is None:
        return {"success": False, "error": err}

    try:
        msp = doc.modelspace()
        rooms = []
        doors_windows = []
        total_wall_length = 0.0

        for e in msp:
            dtype = e.dxftype()
            layer = e.get_dxf_attrib("layer", "").lower()

            if dtype == "LWPOLYLINE":
                pts = list(e.get_points("xy"))
                if e.closed and len(pts) >= 3:
                    poly_area = abs(area(pts))
                    perimeter = sum(
                        np.sqrt(
                            (pts[i][0] - pts[(i + 1) % len(pts)][0]) ** 2
                            + (pts[i][1] - pts[(i + 1) % len(pts)][1]) ** 2
                        )
                        for i in range(len(pts))
                    )
                    is_wall = any(kw in layer for kw in ["wall", "mauer", "wand"])
                    rooms.append(
                        {
                            "layer": e.get_dxf_attrib("layer", ""),
                            "area_m2": round(poly_area / 1_000_000, 3),
                            "perimeter_m": round(perimeter / 1000, 3),
                            "vertex_count": len(pts),
                            "likely_type": "wall_outline" if is_wall else "room",
                        }
                    )
                    if not is_wall:
                        total_wall_length += perimeter / 1000
                elif not e.closed and len(pts) >= 2:
                    length = sum(
                        np.sqrt((pts[i][0] - pts[i + 1][0]) ** 2 + (pts[i][1] - pts[i + 1][1]) ** 2)
                        for i in range(len(pts) - 1)
                    )
                    total_wall_length += length / 1000

            elif dtype == "LINE":
                dx = e.dxf.end.x - e.dxf.start.x
                dy = e.dxf.end.y - e.dxf.start.y
                total_wall_length += np.sqrt(dx * dx + dy * dy) / 1000

            elif dtype == "INSERT":
                block_name = e.dxf.name.lower()
                if any(
                    kw in block_name
                    for kw in ["door", "tu__r", "porte", "porta", "window", "fenster", "fenetre", "finestra"]
                ):
                    doors_windows.append(
                        {
                            "block": e.dxf.name,
                            "layer": e.get_dxf_attrib("layer", ""),
                            "position": {"x": e.dxf.insert.x, "y": e.dxf.insert.y},
                        }
                    )

        return {
            "success": True,
            "data": {
                "rooms": sorted(rooms, key=lambda r: r.get("area_m2", 0), reverse=True),
                "doors_windows": doors_windows,
                "total_entities": len(rooms) + len(doors_windows),
                "wall_length_m": round(total_wall_length, 2),
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def plan_create(
    filename: Annotated[str, Field(description="Output filename (must end in .dxf).")],
    entities: Annotated[
        list[dict], Field(description="List of entity dicts. Types: line, rect, circle, text, polyline. See examples.")
    ],
    layers: Annotated[
        list[dict] | None,
        Field(
            default=None,
            description="Optional layer definitions: [{'name': 'walls', 'color': 7}, ...]. Auto-created from entities if omitted.",
        ),
    ] = None,
    description: Annotated[str, Field(default="", description="Optional description stored in depot metadata.")] = "",
) -> dict:
    """
    Create a new DXF file from primitive entities and store it in the depot.

    Supported entity types:
    - line:   {"type": "line", "x1": 0, "y1": 0, "x2": 100, "y2": 0, "layer": "walls"}
    - rect:   {"type": "rect", "x": 10, "y": 10, "w": 80, "h": 60, "layer": "rooms"}
    - circle: {"type": "circle", "cx": 50, "cy": 50, "r": 20, "layer": "columns"}
    - text:   {"type": "text", "x": 50, "y": 50, "content": "Label", "height": 5, "layer": "labels"}
    - polyline: {"type": "polyline", "points": [[0,0], [100,0], [100,50], [0,50]], "closed": true, "layer": "walls"}

    ## Return Format
    {"success": bool, "filename": str, "data": {"size_kb": float, "entity_count": int}}

    ## Examples
    await plan_create(
        filename="my_plan.dxf",
        entities=[{"type": "rect", "x": 0, "y": 0, "w": 100, "h": 80, "layer": "walls"}],
        layers=[{"name": "walls", "color": 7}],
        description="Simple 100x80 room"
    )
    """
    import ezdxf
    from ezdxf.math import Vec2

    if not filename.lower().endswith(".dxf"):
        filename += ".dxf"

    path = os.path.join(DEPOT_DIR, filename)
    if os.path.isfile(path):
        return {
            "success": False,
            "error": f"File '{filename}' already exists in depot. Delete or choose a different name.",
        }

    try:
        doc = ezdxf.new("R2010")
        msp = doc.modelspace()

        # Create layers
        layer_defs = layers or []
        used_layers = set()
        for ent in entities:
            if "layer" in ent:
                used_layers.add(ent["layer"])
        for name in used_layers:
            if name not in [ld["name"] for ld in layer_defs]:
                layer_defs.append({"name": name, "color": 7})
        for ld in layer_defs:
            doc.layers.add(name=ld["name"], dxfattribs={"color": ld.get("color", 7)})

        # Draw entities
        count = 0
        for ent in entities:
            etype = ent.get("type", "")
            layer = ent.get("layer", "0")
            try:
                if etype == "line":
                    msp.add_line((ent["x1"], ent["y1"]), (ent["x2"], ent["y2"]), dxfattribs={"layer": layer})
                    count += 1
                elif etype == "rect":
                    x, y, w, h = ent["x"], ent["y"], ent["w"], ent["h"]
                    msp.add_lwpolyline(
                        [(x, y), (x + w, y), (x + w, y + h), (x, y + h)], close=True, dxfattribs={"layer": layer}
                    )
                    count += 1
                elif etype == "circle":
                    msp.add_circle((ent["cx"], ent["cy"]), ent["r"], dxfattribs={"layer": layer})
                    count += 1
                elif etype == "text":
                    msp.add_text(ent["content"], dxfattribs={"layer": layer}).set_pos(
                        (ent["x"], ent["y"]), align="LEFT"
                    )
                    count += 1
                elif etype == "polyline":
                    pts = [Vec2(p[0], p[1]) for p in ent.get("points", [])]
                    if len(pts) >= 2:
                        msp.add_lwpolyline(pts, close=ent.get("closed", False), dxfattribs={"layer": layer})
                        count += 1
            except Exception as e:
                logger.warning("Failed to add entity %s: %s", etype, e)

        doc.saveas(path)

        meta = {"created": datetime.now().isoformat(), "description": description, "tags": [], "entity_count": count}
        _write_meta(filename, meta)

        return {
            "success": True,
            "filename": filename,
            "data": {"size_kb": round(os.path.getsize(path) / 1024, 1), "entity_count": count},
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def plan_depot() -> dict:
    """
    List all DXF files in the local CAD depot with metadata.

    ## Return Format
    {"success": bool, "data": {"files": [{"name": ..., "size_kb": ..., "modified": ..., "meta": {...}}]}}

    ## Examples
    await plan_depot()
    """
    return {"success": True, "data": {"files": _depot_list()}}


def register(mcp):
    mcp.tool(annotations=_README_ONLY, version="0.3.0")(plan_info)
    mcp.tool(annotations=_MUTATING, version="0.3.0")(plan_to_svg)
    mcp.tool(annotations=_MUTATING, version="0.3.0")(plan_extrude)
    mcp.tool(annotations=_MUTATING, version="0.3.0")(plan_export)
    mcp.tool(annotations=_README_ONLY, version="0.3.0")(plan_analyse)
    mcp.tool(annotations=_MUTATING, version="0.3.0")(plan_create)
    mcp.tool(annotations=_README_ONLY, version="0.3.0")(plan_depot)
