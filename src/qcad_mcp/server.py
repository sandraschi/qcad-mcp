"""
FastMCP 3.2 Unified Gateway for QCAD DXF/DWG operations.

Architecture:
  DXF/DWG file → ezdxf parser → JSON entities → SVG preview / STL extrusion / room analysis.

The server uses ezdxf (pure Python, MIT) for DXF parsing. No external CAD binary required.
QCAD Pro CLI integration (dwg2pdf, dwg2svg) is optional and auto-detected.
"""

import asyncio
import collections
import json
import logging
import os
import subprocess
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Annotated

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastmcp import FastMCP
from pydantic import BaseModel, Field

logger = logging.getLogger("qcad-mcp")

# ── Config ───────────────────────────────────────────────────────────────────

QCAD_PRO_PATH = os.environ.get(
    "QCAD_PRO_PATH",
    os.path.join(os.environ.get("PROGRAMFILES", "C:\\Program Files"), "QCAD", "qcad.exe"),
)
DEPOT_DIR = os.environ.get(
    "QCAD_MCP_DEPOT",
    os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "qcad-mcp", "depot"),
)
OUTPUT_DIR = os.environ.get(
    "QCAD_MCP_OUTPUT",
    os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "qcad-mcp", "output"),
)
os.makedirs(DEPOT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

EXT_DXF = {".dxf", ".dwg"}


# ── Lifespan ─────────────────────────────────────────────────────────────────

_state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    _state["qcad_pro_ok"] = os.path.isfile(QCAD_PRO_PATH) or os.path.isfile(QCAD_PRO_PATH + ".exe")
    _state["qcad_pro_path"] = QCAD_PRO_PATH
    _state["depot_dir"] = DEPOT_DIR
    _state["output_dir"] = OUTPUT_DIR
    _state["ezdxf_version"] = _get_ezdxf_version()
    logger.info("QCAD MCP startup — ezdxf %s, depot: %s", _state["ezdxf_version"], DEPOT_DIR)
    yield


def _get_ezdxf_version() -> str:
    try:
        import ezdxf
        return ezdxf.__version__
    except Exception:
        return "unknown"


# ── FastAPI App ──────────────────────────────────────────────────────────────

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

mcp = FastMCP.from_fastapi(app, name="QCAD MCP")


# ── File Metadata ────────────────────────────────────────────────────────────


def _meta_path(filename: str) -> str:
    return os.path.join(DEPOT_DIR, f"{filename}.meta.json")


def _read_meta(filename: str) -> dict:
    mp = _meta_path(filename)
    if os.path.isfile(mp):
        try:
            with open(mp) as f:
                return json.load(f)
        except Exception:
            logger.debug("Failed to read meta for %s", filename, exc_info=True)
    return {}


def _write_meta(filename: str, meta: dict):
    with open(_meta_path(filename), "w") as f:
        json.dump(meta, f, indent=2, default=str)


def _ensure_meta(filename: str):
    meta = _read_meta(filename)
    changed = False
    if "created" not in meta:
        meta["created"] = datetime.now().isoformat()
        changed = True
    if "description" not in meta:
        meta["description"] = ""
        changed = True
    if "tags" not in meta:
        meta["tags"] = []
        changed = True
    if changed:
        _write_meta(filename, meta)
    return meta


def _depot_list() -> list[dict]:
    files = {}
    for f in os.listdir(DEPOT_DIR):
        fp = os.path.join(DEPOT_DIR, f)
        if not os.path.isfile(fp):
            continue
        _base, ext = os.path.splitext(f)
        if ext == ".meta.json":
            continue
        if ext not in EXT_DXF and ext != ".dwg":
            continue
        meta = _ensure_meta(f)
        files[f] = {
            "name": f,
            "size_bytes": os.path.getsize(fp),
            "size_kb": round(os.path.getsize(fp) / 1024, 1),
            "modified": datetime.fromtimestamp(os.path.getmtime(fp)).isoformat(),
            "meta": meta,
        }
    return sorted(files.values(), key=lambda x: x["modified"], reverse=True)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _load_dxf(file_name: str):
    import ezdxf

    path = os.path.join(DEPOT_DIR, file_name)
    if not os.path.isfile(path):
        return None, f"File '{file_name}' not found in depot."

    try:
        doc = ezdxf.readfile(path)
        return doc, None
    except Exception as e:
        return None, f"Failed to read DXF: {e}"


def _doc_to_info(doc) -> dict:
    msp = doc.modelspace()
    entity_counts = {}
    for e in msp:
        entity_counts[e.dxftype()] = entity_counts.get(e.dxftype(), 0) + 1

    layers = []
    for layer in doc.layers:
        layers.append({
            "name": layer.dxf.name,
            "color": layer.dxf.color,
            "frozen": getattr(layer, "is_frozen", lambda: False)(),
            "locked": getattr(layer, "is_locked", lambda: False)(),
        })

    blocks = [b.name for b in doc.blocks]

    bbox = None
    try:
        from ezdxf.bbox import extents
        bbox_rect = extents(msp)
        if bbox_rect.has_data:
            bbox = {"xmin": bbox_rect.extmin.x, "ymin": bbox_rect.extmin.y, "xmax": bbox_rect.extmax.x, "ymax": bbox_rect.extmax.y}
    except Exception:
        logger.debug("Failed to compute bounding box", exc_info=True)

    return {
        "layers": layers,
        "layer_count": len(layers),
        "entity_counts": entity_counts,
        "entity_total": sum(entity_counts.values()),
        "blocks": blocks,
        "block_count": len(blocks),
        "bounding_box": bbox,
        "dxf_version": doc.dxfversion,
    }


# ── MCP Tools ────────────────────────────────────────────────────────────────

_READ_ONLY = {"readonly": True}


@mcp.tool(annotations=_READ_ONLY)
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


@mcp.tool()
async def plan_to_svg(
    file_name: Annotated[str, Field(description="DXF filename in the depot.")],
    output_name: Annotated[str, Field(default="output.svg", description="Desired output SVG filename.")] = "output.svg",
    layers: Annotated[list[str] | None, Field(default=None, description="Optional list of layer names to include. All layers if omitted.")] = None,
    background: Annotated[str, Field(default="white", description="Background colour: white, black, or hex (e.g. #1a1a1a).")] = "white",
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


@mcp.tool()
async def plan_extrude(
    file_name: Annotated[str, Field(description="DXF filename in the depot.")],
    output_name: Annotated[str, Field(default="extruded.stl", description="Desired output STL filename.")] = "extruded.stl",
    wall_height: Annotated[float, Field(default=3.0, description="Wall extrusion height in metres (default 3.0m).")] = 3.0,
    wall_thickness: Annotated[float, Field(default=0.3, description="Wall thickness in metres (default 0.3m).")] = 0.3,
    wall_layers: Annotated[list[str] | None, Field(default=None, description="Layer names to treat as walls. Auto-detected if omitted (matches 'wall', 'mauer', 'wand').")] = None,
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
                wall_segments.append({"type": "line", "start": (e.dxf.start.x, e.dxf.start.y), "end": (e.dxf.end.x, e.dxf.end.y)})
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
            return {"success": False, "error": "No wall entities found. Try specifying wall_layers or use a DXF with LINE/LWPOLYLINE entities."}

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
            v = np.array([
                [x1 - nx * hw, y1 - ny * hw, 0], [x1 + nx * hw, y1 + ny * hw, 0],
                [x2 + nx * hw, y2 + ny * hw, 0], [x2 - nx * hw, y2 - ny * hw, 0],
                [x1 - nx * hw, y1 - ny * hw, wall_height], [x1 + nx * hw, y1 + ny * hw, wall_height],
                [x2 + nx * hw, y2 + ny * hw, wall_height], [x2 - nx * hw, y2 - ny * hw, wall_height],
            ])
            triangles = np.array([
                [v[0], v[1], v[2]], [v[0], v[2], v[3]],
                [v[4], v[6], v[5]], [v[4], v[7], v[6]],
                [v[0], v[3], v[7]], [v[0], v[7], v[4]],
                [v[1], v[5], v[6]], [v[1], v[6], v[2]],
                [v[0], v[4], v[5]], [v[0], v[5], v[1]],
                [v[3], v[2], v[6]], [v[3], v[6], v[7]],
            ])
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
                "vertices": len(combined.points), "faces": len(combined.data),
                "wall_count": len(wall_segments), "size_kb": round(os.path.getsize(stl_path) / 1024, 1),
                "wall_height_m": wall_height, "wall_thickness_m": wall_thickness,
            },
        }
    except Exception as e:
        logger.exception("plan_extrude failed")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def plan_export(
    file_name: Annotated[str, Field(description="DXF filename in the depot.")],
    format: Annotated[str, Field(default="svg", description="Output format: svg, pdf, or png.")] = "svg",
    output_name: Annotated[str, Field(default="", description="Output filename. Auto-generated if empty.")] = "",
) -> dict:
    """
    Export a DXF file to SVG, PDF, or PNG.

    Uses ezdxf+matplotlib for SVG/PNG, or QCAD Pro CLI for high-fidelity PDF if installed.

    ## Return Format
    {"success": bool, "output": str, "data": {"size_kb": float, "backend": str}}

    ## Examples
    await plan_export(file_name="floorplan.dxf", format="svg")
    """
    ext_map = {"svg": ".svg", "pdf": ".pdf", "png": ".png"}
    if format not in ext_map:
        return {"success": False, "error": f"Unknown format: {format}. Use svg, pdf, or png."}

    out_name = output_name or f"{Path(file_name).stem}{ext_map[format]}"
    out_path = os.path.join(OUTPUT_DIR, out_name)

    qcad_ok = _state.get("qcad_pro_ok", False)
    qcad_path = _state.get("qcad_pro_path", "")

    if qcad_ok and format == "pdf":
        in_path = os.path.join(DEPOT_DIR, file_name)
        if os.path.isfile(in_path):
            try:
                proc = subprocess.run(  # noqa: S603
                    [qcad_path, "-no-gui", "-autostart", "scripts/Pro/Tools/Dwg2Pdf/Dwg2Pdf.js",
                     "-o", out_path, in_path],
                    capture_output=True, text=True, timeout=120,
                )
                if proc.returncode == 0 and os.path.isfile(out_path):
                    return {"success": True, "output": out_name, "data": {"size_kb": round(os.path.getsize(out_path) / 1024, 1), "backend": "qcad_pro"}}
            except Exception as e:
                logger.warning("QCAD Pro CLI error: %s", e)

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

        return {"success": True, "output": out_name, "data": {"size_kb": round(os.path.getsize(out_path) / 1024, 1), "backend": "ezdxf+matplotlib"}}
    except Exception as e:
        return {"success": False, "error": f"Export failed: {e}"}


@mcp.tool(annotations=_READ_ONLY)
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
                        np.sqrt((pts[i][0] - pts[(i + 1) % len(pts)][0]) ** 2 +
                                (pts[i][1] - pts[(i + 1) % len(pts)][1]) ** 2)
                        for i in range(len(pts))
                    )
                    is_wall = any(kw in layer for kw in ["wall", "mauer", "wand"])
                    rooms.append({
                        "layer": e.get_dxf_attrib("layer", ""),
                        "area_m2": round(poly_area / 1_000_000, 3),
                        "perimeter_m": round(perimeter / 1000, 3),
                        "vertex_count": len(pts),
                        "likely_type": "wall_outline" if is_wall else "room",
                    })
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
                if any(kw in block_name for kw in ["door", "tu__r", "porte", "porta", "window", "fenster", "fenetre", "finestra"]):
                    doors_windows.append({
                        "block": e.dxf.name, "layer": e.get_dxf_attrib("layer", ""),
                        "position": {"x": e.dxf.insert.x, "y": e.dxf.insert.y},
                    })

        return {"success": True, "data": {
            "rooms": sorted(rooms, key=lambda r: r.get("area_m2", 0), reverse=True),
            "doors_windows": doors_windows,
            "total_entities": len(rooms) + len(doors_windows),
            "wall_length_m": round(total_wall_length, 2),
        }}
    except Exception as e:
        logger.exception("plan_analyse failed")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def plan_create(
    filename: Annotated[str, Field(description="Output filename (must end in .dxf).")],
    entities: Annotated[list[dict], Field(description="List of entity dicts. Types: line, rect, circle, text, polyline. See examples.")],
    layers: Annotated[list[dict] | None, Field(default=None, description="Optional layer definitions: [{'name': 'walls', 'color': 7}, ...]. Auto-created from entities if omitted.")] = None,
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
        return {"success": False, "error": f"File '{filename}' already exists in depot. Delete or choose a different name."}

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
                    msp.add_lwpolyline([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], close=True, dxfattribs={"layer": layer})
                    count += 1
                elif etype == "circle":
                    msp.add_circle((ent["cx"], ent["cy"]), ent["r"], dxfattribs={"layer": layer})
                    count += 1
                elif etype == "text":
                    msp.add_text(ent["content"], dxfattribs={"layer": layer}).set_pos((ent["x"], ent["y"]), align="LEFT")
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


@mcp.tool(annotations=_READ_ONLY)
async def plan_depot() -> dict:
    """
    List all DXF files in the local CAD depot with metadata.

    ## Return Format
    {"success": bool, "data": {"files": [{"name": ..., "size_kb": ..., "modified": ..., "meta": {...}}]}}

    ## Examples
    await plan_depot()
    """
    return {"success": True, "data": {"files": _depot_list()}}


# ── REST Endpoints — Depot CRUD ─────────────────────────────────────────────


@app.get("/api/v1/depot")
async def depot_list():
    return {"files": _depot_list()}


@app.get("/api/v1/depot/{filename}")
async def depot_get(filename: str):
    path = os.path.join(DEPOT_DIR, filename)
    if not os.path.isfile(path):
        raise HTTPException(404, f"File '{filename}' not found in depot.")
    ext = Path(filename).suffix.lower()
    media_types = {".dxf": "application/dxf", ".dwg": "application/acad"}
    return FileResponse(path, media_type=media_types.get(ext, "application/octet-stream"), filename=filename)


@app.put("/api/v1/depot/{filename}")
async def depot_rename(filename: str, body: dict):
    new_name = body.get("name", "")
    description = body.get("description")
    tags = body.get("tags")

    old_path = os.path.join(DEPOT_DIR, filename)
    if not os.path.isfile(old_path):
        raise HTTPException(404, f"File '{filename}' not found.")

    if new_name and new_name != filename:
        new_path = os.path.join(DEPOT_DIR, new_name)
        if os.path.isfile(new_path):
            raise HTTPException(409, f"File '{new_name}' already exists.")
        os.rename(old_path, new_path)
        os.rename(_meta_path(filename), _meta_path(new_name))
        filename = new_name

    if description is not None or tags is not None:
        meta = _read_meta(filename)
        if description is not None:
            meta["description"] = description
        if tags is not None:
            meta["tags"] = tags
        _write_meta(filename, meta)

    return {"success": True, "filename": filename}


@app.delete("/api/v1/depot/{filename}")
async def depot_delete(filename: str):
    path = os.path.join(DEPOT_DIR, filename)
    if not os.path.isfile(path):
        raise HTTPException(404, f"File '{filename}' not found.")
    os.remove(path)
    mp = _meta_path(filename)
    if os.path.isfile(mp):
        os.remove(mp)
    logger.info("Deleted %s from depot", filename)
    return {"success": True, "filename": filename}


# ── REST Endpoints — DXF Creation ────────────────────────────────────────────


class CreateDxfRequest(BaseModel):
    filename: str = Field(description="Output DXF filename.")
    entities: list[dict] = Field(description="List of entity dicts (line, rect, circle, text, polyline).")
    layers: list[dict] | None = Field(default=None, description="Optional layer definitions.")
    description: str = Field(default="", description="Optional file description.")


@app.post("/api/v1/depot/create")
async def depot_create(req: CreateDxfRequest):
    result = await plan_create(
        filename=req.filename,
        entities=req.entities,
        layers=req.layers,
        description=req.description,
    )
    if result.get("success"):
        return result
    raise HTTPException(400, result.get("error", "Creation failed"))


# ── REST Endpoints — Upload/Download Legacy ─────────────────────────────────


@app.post("/api/v1/upload")
async def upload_file(file: UploadFile):
    if not file.filename:
        raise HTTPException(400, "No filename")
    ext = Path(file.filename).suffix.lower()
    if ext not in EXT_DXF:
        raise HTTPException(400, f"Unsupported format: {ext}. Use .dxf or .dwg.")
    dest = os.path.join(DEPOT_DIR, file.filename)
    if os.path.isfile(dest):
        raise HTTPException(409, f"File '{file.filename}' already exists. Delete or rename first.")
    content = await file.read()
    with open(dest, "wb") as f:
        f.write(content)
    _ensure_meta(file.filename)
    logger.info("Uploaded %s (%d bytes) to depot", file.filename, len(content))
    return {"success": True, "filename": file.filename, "size_bytes": len(content), "path": dest}


@app.get("/api/v1/download/{filename}")
async def download_file(filename: str):
    path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.isfile(path):
        raise HTTPException(404, f"File {filename} not found.")
    ext = Path(filename).suffix.lower()
    media_types = {".svg": "image/svg+xml", ".stl": "application/sla", ".pdf": "application/pdf", ".png": "image/png"}
    return FileResponse(path, media_type=media_types.get(ext, "application/octet-stream"), filename=filename)


@app.get("/api/v1/files")
async def list_files():
    uploads = []
    for f in os.listdir(DEPOT_DIR):
        fp = os.path.join(DEPOT_DIR, f)
        if os.path.isfile(fp) and not f.endswith(".meta.json"):
            uploads.append({"name": f, "size_kb": round(os.path.getsize(fp) / 1024, 1)})
    outputs = [{"name": f, "size_kb": round(os.path.getsize(os.path.join(OUTPUT_DIR, f)) / 1024, 1)} for f in os.listdir(OUTPUT_DIR) if os.path.isfile(os.path.join(OUTPUT_DIR, f))]
    return {"uploads": uploads, "outputs": outputs}


# ── REST Endpoints — Tool Bridge ──────────────────────────────────────────────


class ToolRequest(BaseModel):
    tool: str = Field(description="Tool name: plan_info, plan_to_svg, plan_extrude, plan_export, plan_analyse, plan_create, plan_depot")
    arguments: dict = Field(default_factory=dict, description="Tool arguments as a dict")


@app.post("/api/v1/control/tool")
async def execute_tool(req: ToolRequest):
    args = req.arguments or {}
    t = req.tool

    if t == "plan_info":
        return await plan_info(file_name=args.get("file_name", ""))
    elif t == "plan_to_svg":
        return await plan_to_svg(file_name=args.get("file_name", ""), output_name=args.get("output_name", "output.svg"), layers=args.get("layers"), background=args.get("background", "white"))
    elif t == "plan_extrude":
        return await plan_extrude(file_name=args.get("file_name", ""), output_name=args.get("output_name", "extruded.stl"), wall_height=args.get("wall_height", 3.0), wall_thickness=args.get("wall_thickness", 0.3), wall_layers=args.get("wall_layers"))
    elif t == "plan_export":
        return await plan_export(file_name=args.get("file_name", ""), format=args.get("format", "svg"), output_name=args.get("output_name", ""))
    elif t == "plan_analyse":
        return await plan_analyse(file_name=args.get("file_name", ""))
    elif t == "plan_create":
        return await plan_create(filename=args.get("filename", ""), entities=args.get("entities", []), layers=args.get("layers"), description=args.get("description", ""))
    elif t == "plan_depot":
        return await plan_depot()
    else:
        raise HTTPException(400, f"Unknown tool: {t}")


# ── Log Ring Buffer ──────────────────────────────────────────────────────────

LOG_RING = collections.deque(maxlen=2000)


class LogHandler(logging.Handler):
    def emit(self, record):
        LOG_RING.append(self.format(record))


_log_handler = LogHandler()
_log_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
logger.addHandler(_log_handler)


@app.get("/api/v1/logs/stream")
async def stream_logs():
    async def gen():
        for line in list(LOG_RING):
            yield f"data: {line}\n\n"
        idx = len(LOG_RING)
        while True:
            if idx < len(LOG_RING):
                yield f"data: {LOG_RING[idx]}\n\n"
                idx += 1
            await asyncio.sleep(0.1)
    return StreamingResponse(gen(), media_type="text/event-stream")


# ── Chat / LLM ───────────────────────────────────────────────────────────────

_llm_settings = {"ollama_url": "http://192.168.1.11:11434", "model": "gemma3:1b"}


class ChatRequest(BaseModel):
    messages: list[dict] = []
    system: str = ""
    provider: str = "ollama"
    model: str = "gemma3:1b"


class SettingsUpdate(BaseModel):
    ollama_url: str | None = None
    model: str | None = None
    qcad_pro_path: str | None = None
    default_wall_height: float | None = None
    default_wall_thickness: float | None = None


_app_settings = {"default_wall_height": 3.0, "default_wall_thickness": 0.3}


@app.get("/api/v1/settings")
async def get_settings():
    return {**_llm_settings, **_app_settings, "qcad_pro_path": _state.get("qcad_pro_path", ""), "qcad_pro_ok": _state.get("qcad_pro_ok", False)}


@app.put("/api/v1/settings")
async def update_settings(body: SettingsUpdate):
    if body.ollama_url:
        _llm_settings["ollama_url"] = body.ollama_url
    if body.model:
        _llm_settings["model"] = body.model
    if body.qcad_pro_path:
        _state["qcad_pro_path"] = body.qcad_pro_path
        _state["qcad_pro_ok"] = os.path.isfile(body.qcad_pro_path)
    if body.default_wall_height is not None:
        _app_settings["default_wall_height"] = body.default_wall_height
    if body.default_wall_thickness is not None:
        _app_settings["default_wall_thickness"] = body.default_wall_thickness
    return {**_llm_settings, **_app_settings, "qcad_pro_path": _state.get("qcad_pro_path", ""), "qcad_pro_ok": _state.get("qcad_pro_ok", False)}


@app.post("/api/v1/chat")
async def chat_completion(req: ChatRequest):
    url = req.provider == "ollama" and f"{_llm_settings.get('ollama_url', 'http://192.168.1.11:11434')}/api/chat"
    model = req.model or _llm_settings.get("model", "gemma3:1b")
    if not url:
        return {"content": "Only Ollama provider is supported currently."}
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(url, json={
                "model": model,
                "messages": [{"role": "system", "content": req.system or "You are a CAD and floor plan expert."}, *req.messages],
                "stream": False,
            })
            data = r.json()
            return {"content": (data.get("message") or {}).get("content", "") or data.get("response", "")}
    except Exception as e:
        logger.error("Chat error: %s", e)
        return {"content": f"Error: {e}"}


# ── Entry point ──────────────────────────────────────────────────────────────


async def _run_stdio():
    await mcp.run_stdio_async()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="QCAD MCP Server")
    parser.add_argument("--mode", choices=["stdio", "http", "dual"], default="stdio")
    parser.add_argument("--host", default="0.0.0.0")  # noqa: S104
    parser.add_argument("--port", type=int, default=10966)
    args = parser.parse_args()

    if args.mode == "stdio":
        asyncio.run(_run_stdio())
    else:
        logger.info("Starting QCAD MCP on %s:%s", args.host, args.port)
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
