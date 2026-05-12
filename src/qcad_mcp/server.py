"""
FastMCP 3.2 Unified Gateway for QCAD DXF/DWG operations with DWG support and plan_modify.

Architecture:
  DXF/DWG file → ezdxf parser → JSON entities → SVG preview / STL extrusion / room analysis / layer modify.

The server uses ezdxf (pure Python, MIT) for DXF parsing. No external CAD binary required.
QCAD Pro CLI integration (dwg2pdf, dwg2svg, DWG↔DXF conversion) is optional and auto-detected.
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
from bs4 import BeautifulSoup
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

    # Auto-convert DWG to temp DXF
    if _is_dwg(file_name):
        if not _qcad_pro_available():
            return None, "DWG files require QCAD Pro. Set QCAD_PRO_PATH or convert to DXF first."
        dxf_path = os.path.join(OUTPUT_DIR, Path(file_name).stem + "_converted.dxf")
        if not _qcad_pro_convert(path, dxf_path, "DXF"):
            return None, "QCAD Pro DWG→DXF conversion failed."
        path = dxf_path

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


def _is_dwg(file_name: str) -> bool:
    return Path(file_name).suffix.lower() == ".dwg"


def _qcad_pro_available() -> bool:
    path = os.environ.get("QCAD_PRO_PATH", os.path.join(os.environ.get("PROGRAMFILES", "C:\\Program Files"), "QCAD", "qcad.exe"))
    return os.path.isfile(path) or os.path.isfile(path + ".exe")


def _qcad_pro_convert(input_path: str, output_path: str, fmt: str = "DXF") -> bool:
    """Convert DWG↔DXF using QCAD Pro CLI. Returns True on success."""
    import subprocess
    path = QCAD_PRO_PATH if os.path.isfile(QCAD_PRO_PATH) else QCAD_PRO_PATH + ".exe"
    try:
        r = subprocess.run([path, "-no-gui", f"-export-{fmt.lower()}", output_path, input_path],
                          capture_output=True, text=True, timeout=60)
        return r.returncode == 0 and os.path.isfile(output_path)
    except Exception as e:
        logger.warning("QCAD Pro convert failed: %s", e)
        return False


def _ensure_dxf(file_name: str) -> tuple[str | None, str | None]:
    """If DWG, convert to temp DXF. Returns (dxf_path_or_original, error)."""
    if not _is_dwg(file_name):
        return os.path.join(DEPOT_DIR, file_name), None
    if not _qcad_pro_available():
        return None, "DWG files require QCAD Pro. Set QCAD_PRO_PATH or convert to DXF first."
    dwg_path = os.path.join(DEPOT_DIR, file_name)
    dxf_path = os.path.join(OUTPUT_DIR, Path(file_name).stem + "_converted.dxf")
    if _qcad_pro_convert(dwg_path, dxf_path, "DXF"):
        return dxf_path, None
    return None, "QCAD Pro conversion failed. Check the file or QCAD installation."


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
                proc = subprocess.run(
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


@mcp.tool()
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


_ENTITY_TYPES_HELP = "line: {'type':'line','layer':'Walls','x1':0,'y1':0,'x2':100,'y2':100}. rect: {'type':'rect','x':0,'y':0,'w':100,'h':80,'layer':'Walls'}. circle: {'type':'circle','cx':50,'cy':50,'r':20,'layer':'Columns'}"


@mcp.tool()
async def plan_modify(
    file_name: Annotated[str, Field(description="DXF or DWG filename in the depot.")],
    operations: Annotated[list[dict], Field(description="""List of modification operations. Each operation has:
- op: "delete" (delete matching entities by layer/type),
       "offset" (offset lines/polylines by distance),
       "layer-set-color" (set layer colour),
       "layer-rename" (rename layer),
       "layer-freeze" / "layer-thaw",
       "layer-lock" / "layer-unlock",
       "merge-layers" (combine two layers: {op:"merge-layers", source:"LayerA", target:"LayerB"})
- type_filter: optional DXF type filter (e.g. "LINE", "CIRCLE", "TEXT")
- layer_filter: optional layer name filter
""")],
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
                        except Exception:
                            pass
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
                            summary.append(f"Renamed layer '{old}' → '{new}'")
                else:
                    summary.append("layer-rename requires old_name and new_name")

            elif op_type in ("layer-freeze", "layer-thaw"):
                freeze = op_type == "layer-freeze"
                for layer in doc.layers:
                    if not layer_filter or layer.dxf.name == layer_filter:
                        try:
                            if hasattr(layer, "is_frozen"):
                                layer.is_frozen = freeze
                        except Exception:
                            pass
                summary.append(f"{'Froze' if freeze else 'Thawed'} layer '{layer_filter or 'all'} '")

            elif op_type == "layer-lock" or op_type == "layer-unlock":
                lock = op_type == "layer-lock"
                for layer in doc.layers:
                    if not layer_filter or layer.dxf.name == layer_filter:
                        try:
                            if hasattr(layer, "is_locked"):
                                layer.is_locked = lock
                        except Exception:
                            pass
                summary.append(f"{'Locked' if lock else 'Unlocked'} layer '{layer_filter or 'all'} '")

            elif op_type == "merge-layers":
                src = op.get("source", "")
                tgt = op.get("target", "")
                if src and tgt:
                    for e in list(msp):
                        if e.dxf.layer == src:
                            e.dxf.layer = tgt
                    try:
                        doc.layers.remove(src)
                    except Exception:
                        pass
                    summary.append(f"Merged layer '{src}' → '{tgt}'")
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


# ── CAD Block Search ──────────────────────────────────────────────────────────

_BLOCK_CATEGORIES = [
    {"id": "", "label": "All"},
    {"id": "furniture", "label": "Furniture"},
    {"id": "doors-windows", "label": "Doors & Windows"},
    {"id": "kitchens", "label": "Kitchens"},
    {"id": "bathrooms", "label": "Bathrooms"},
    {"id": "lighting", "label": "Lighting"},
    {"id": "electrical", "label": "Electrical"},
    {"id": "plumbing", "label": "Plumbing"},
    {"id": "stairs", "label": "Stairs"},
    {"id": "trees-plants", "label": "Trees & Plants"},
    {"id": "vehicles", "label": "Vehicles"},
    {"id": "people", "label": "People & Scale Figures"},
    {"id": "sports", "label": "Sports & Recreation"},
    {"id": "landscape", "label": "Landscape"},
    {"id": "symbols", "label": "CAD Symbols"},
    {"id": "title-blocks", "label": "Title Blocks"},
    {"id": "tables", "label": "Tables & Chairs"},
    {"id": "beds", "label": "Beds"},
    {"id": "sofas", "label": "Sofas & Seating"},
    {"id": "shelves", "label": "Shelves & Storage"},
    {"id": "office", "label": "Office"},
    {"id": "industrial", "label": "Industrial Equipment"},
    {"id": "machinery", "label": "Machinery"},
    {"id": "floor-plans", "label": "Sample Floor Plans"},
    {"id": "detailing", "label": "Construction Detailing"},
]

_BLOCK_HEADERS = {"User-Agent": "qcad-mcp/0.1.0 (MCP server; +https://github.com/sandraschi/qcad-mcp)"}


async def _search_cadblocksfree(query: str, category: str, limit: int) -> list[dict]:
    """Search cadblocksfree.com for CAD blocks."""
    results = []
    url = f"https://www.cadblocksfree.com/en/search/{query.replace(' ', '-')}/" if query else "https://www.cadblocksfree.com/en/cad-blocks/"
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            r = await client.get(url, headers=_BLOCK_HEADERS)
            soup = BeautifulSoup(r.text, "html.parser")
            for article in soup.select("article.grid-item, div.portfolio-item, div.cad-item, li.grid-item")[:limit]:
                title_el = article.select_one("h3 a, h2 a, .title a, a")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                href = title_el.get("href", "")
                img_el = article.select_one("img")
                img = img_el.get("src", "") if img_el else ""
                cat_el = article.select_one(".category, .cat, .term")
                cat = cat_el.get_text(strip=True) if cat_el else category or "General"
                results.append({
                    "title": title[:100],
                    "source": "cadblocksfree",
                    "url": href if href.startswith("http") else f"https://www.cadblocksfree.com{href}",
                    "image_url": img if img.startswith("http") else f"https://www.cadblocksfree.com{img}" if img else "",
                    "category": cat,
                })
    except Exception as e:
        logger.warning("cadblocksfree search error: %s", e)
    return results


async def _search_biblocad(query: str, category: str, limit: int) -> list[dict]:
    """Search biblocad.com for CAD blocks."""
    results = []
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            r = await client.get(f"https://biblocad.com/search?q={query}", headers=_BLOCK_HEADERS)
            soup = BeautifulSoup(r.text, "html.parser")
            for item in soup.select(".item, .result-item, .search-item, .block-item, tr")[:limit]:
                title_el = item.select_one("a.title, a.name, h3 a, h2 a, td a")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                href = title_el.get("href", "")
                img_el = item.select_one("img")
                img = img_el.get("src", "") if img_el else ""
                results.append({
                    "title": title[:100],
                    "source": "biblocad",
                    "url": href if href.startswith("http") else f"https://biblocad.com{href}",
                    "image_url": img if img.startswith("http") else f"https://biblocad.com{img}" if img else "",
                    "category": category or "General",
                })
    except Exception as e:
        logger.warning("biblocad search error: %s", e)
    return results


async def _search_gallery(query: str, category: str, limit: int) -> list[dict]:
    """Return curated sample floor plans and architectural blocks."""
    samples = {
        "floor-plans": [
            {"title": "Small Apartment Floor Plan (45m²)", "url": "https://www.cadblocksfree.com/en/download/small-apartment-plan.dxf", "category": "Floor Plans"},
            {"title": "Office Layout Open Plan", "url": "https://www.cadblocksfree.com/en/download/office-open-plan.dxf", "category": "Floor Plans"},
            {"title": "Two-Bedroom House Plan (80m²)", "url": "https://www.cadblocksfree.com/en/download/two-bedroom-house.dxf", "category": "Floor Plans"},
            {"title": "Restaurant Floor Plan", "url": "https://www.cadblocksfree.com/en/download/restaurant-plan.dxf", "category": "Floor Plans"},
            {"title": "Classroom Layout", "url": "https://www.cadblocksfree.com/en/download/classroom.dxf", "category": "Floor Plans"},
        ],
        "doors-windows": [
            {"title": "Door Block Collection (20 types)", "category": "Doors & Windows"},
            {"title": "Window Block Collection (15 types)", "category": "Doors & Windows"},
            {"title": "Sliding Door Details", "category": "Doors & Windows"},
            {"title": "French Door Elevation", "category": "Doors & Windows"},
            {"title": "Garage Door Plan View", "category": "Doors & Windows"},
        ],
        "furniture": [
            {"title": "Sofa Collection (10 styles)", "category": "Furniture"},
            {"title": "Dining Table Sets", "category": "Furniture"},
            {"title": "Bedroom Furniture Pack", "category": "Furniture"},
            {"title": "Bookshelf Units", "category": "Furniture"},
            {"title": "Kitchen Cabinet Layouts", "category": "Furniture"},
        ],
        "bathrooms": [
            {"title": "Bathroom Fixture Blocks", "category": "Bathrooms"},
            {"title": "Shower Cubicle Details", "category": "Bathrooms"},
            {"title": "Toilet & Sink Blocks", "category": "Bathrooms"},
            {"title": "Bathtub Collection", "category": "Bathrooms"},
        ],
        "trees-plants": [
            {"title": "Tree Blocks (Plan View)", "category": "Trees & Plants"},
            {"title": "Plant Pot Collection", "category": "Trees & Plants"},
            {"title": "Garden Layout Elements", "category": "Trees & Plants"},
        ],
    }
    if query:
        results = [item for cat_items in samples.values() for item in cat_items if query.lower() in item["title"].lower()]
    elif category and category in samples:
        results = samples[category]
    else:
        results = [item for cat_items in samples.values() for item in cat_items]
    for r in results:
        r.setdefault("source", "gallery")
        r.setdefault("image_url", "")
        r.setdefault("url", "")
    return results[:limit]


_BLOCK_SOURCES = {
    "cadblocksfree": _search_cadblocksfree,
    "biblocad": _search_biblocad,
    "gallery": _search_gallery,
}


@mcp.tool(annotations={"readonly": True})
async def plan_blocks(
    query: Annotated[str, Field(default="", description="Search query (empty = browse all in category).")] = "",
    category: Annotated[str, Field(default="", description="Category filter: furniture, doors-windows, kitchens, bathrooms, floor-plans, etc.")] = "",
    source: Annotated[str, Field(default="all", description="Source: cadblocksfree, biblocad, gallery, or all")] = "all",
    limit: Annotated[int, Field(default=20, description="Max results.")] = 20,
) -> dict:
    """Search CAD block libraries for architectural blocks, furniture, doors, and sample floor plans.

    Use plan_blocks_download to import a block directly into the local depot.

    ## Return Format
    {"success": bool, "results": list, "source": str}

    ## Examples
    await plan_blocks(query="sofa", category="furniture")
    await plan_blocks(category="floor-plans", limit=5)
    await plan_blocks(query="kitchen")
    """
    all_results = []
    sources = [source] if source != "all" else list(_BLOCK_SOURCES.keys())
    for s in sources:
        if s in _BLOCK_SOURCES:
            results = await _BLOCK_SOURCES[s](query, category, limit)
            all_results.extend(results)
    all_results.sort(key=lambda x: x.get("category", ""))
    return {"success": True, "source": source, "results": all_results[:limit]}


@mcp.tool()
async def plan_blocks_download(
    title: Annotated[str, Field(description="Block title (used as filename).")],
    source: Annotated[str, Field(description="Source from search results.")],
    url: Annotated[str, Field(description="Download URL from search results.")],
) -> dict:
    """Download a CAD block from a library into the local depot.

    After download, use plan_info to inspect or plan_to_svg to preview.

    ## Return Format
    {"success": bool, "filename": str, "size_kb": float, "path": str}

    ## Examples
    await plan_blocks_download(title="Sofa Collection", source="cadblocksfree", url="https://...")
    """
    if not url:
        return {"success": False, "error": "No download URL provided. Browse the source website."}
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            r = await client.get(url, headers=_BLOCK_HEADERS)
            r.raise_for_status()
        safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in title).strip()[:60]
        filename = f"{safe}.dxf"
        path = os.path.join(DEPOT_DIR, filename)
        with open(path, "wb") as f:
            f.write(r.content)
        return {"success": True, "filename": filename, "size_kb": round(len(r.content) / 1024, 1), "path": path}
    except Exception as e:
        logger.error("Block download error: %s", e)
        return {"success": False, "error": f"Download failed: {e}"}


@app.get("/api/v1/blocks/categories")
async def blocks_categories():
    """List CAD block categories."""
    return {"categories": _BLOCK_CATEGORIES}


@app.get("/api/v1/blocks/search")
async def blocks_search(query: str = "", category: str = "", source: str = "all", limit: int = 20):
    """Search CAD block libraries via REST."""
    result = await plan_blocks(query=query, category=category, source=source, limit=limit)
    return result


@app.post("/api/v1/blocks/download")
async def blocks_download(body: dict):
    """Download a CAD block to the depot via REST."""
    result = await plan_blocks_download(
        title=body.get("title", "block"),
        source=body.get("source", "gallery"),
        url=body.get("url", ""),
    )
    return result if result.get("success") else {"success": False, "error": result.get("error", "Download failed")}


@app.post("/api/v1/batch")
async def batch_run(body: dict):
    """Run an MCP tool on all DXF/DWG files in the depot.

    Body: {"tool": "plan_info", "args": {}}  # args are extended per file
    Returns: {"results": [{"file": ..., "success": bool, "data": ...}]}
    """
    tool_name = body.get("tool", "")
    args = body.get("args", {})
    tool_map = {
        "plan_info": plan_info,
        "plan_analyse": plan_analyse,
    }
    if tool_name not in tool_map:
        raise HTTPException(400, f"Batch tool must be one of: {list(tool_map.keys())}")

    ext_ok = {".dxf", ".dwg"}
    files = [f for f in _depot_list() if Path(f["name"]).suffix.lower() in ext_ok]
    if not files:
        raise HTTPException(404, "No DXF/DWG files found in depot")

    results = []
    for f in files:
        fn = f["name"]
        try:
            r = await tool_map[tool_name](file_name=fn, **args)
            results.append({"file": fn, "success": r.get("success", False), "data": r.get("data", {}), "error": r.get("error")})
        except Exception as e:
            results.append({"file": fn, "success": False, "error": str(e)})

    return {"tool": tool_name, "total": len(files), "success_count": sum(1 for r in results if r["success"]), "results": results}


@app.get("/api/v1/layers/{filename}")
async def get_layers(filename: str):
    """Get layers for a DXF/DWG file."""
    doc, err = _load_dxf(filename)
    if doc is None:
        raise HTTPException(404, err)
    info = _doc_to_info(doc)
    return {"success": True, "filename": filename, "layers": info["layers"], "dxf_version": info["dxf_version"]}


@app.post("/api/v1/layers/{filename}")
async def update_layers(filename: str, body: dict):
    """Modify layers on a file."""
    result = await plan_modify(file_name=filename, operations=body.get("operations", []))
    if not result.get("success"):
        raise HTTPException(500, result.get("error", "Layer operation failed"))
    return result


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
    tool: str = Field(description="Tool name: plan_info, plan_to_svg, plan_extrude, plan_export, plan_analyse, plan_create, plan_depot, plan_convert, plan_modify")
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
    elif t == "plan_convert":
        return await plan_convert(file_name=args.get("file_name", ""), output_name=args.get("output_name", ""))
    elif t == "plan_modify":
        return await plan_modify(file_name=args.get("file_name", ""), operations=args.get("operations", []))
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
