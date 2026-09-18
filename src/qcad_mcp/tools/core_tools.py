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
            # ezdxf paints the axes patch CAD-black by default; match it to the
            # requested background or the preview is a black square on white.
            ax.set_facecolor(background)
            fig.patch.set_facecolor(background)
            fig.savefig(svg_path, format="svg", facecolor=background)
            plt.close(fig)
        else:
            ctx = RenderContext(doc)
            fig = plt.figure()
            ax = fig.add_subplot(111)
            out = MatplotlibBackend(ax)
            frontend = Frontend(ctx, out)
            frontend.draw_layout(msp, finalize=True)
            ax.set_facecolor(background)
            fig.patch.set_facecolor(background)
            fig.savefig(svg_path, format="svg", facecolor=background)
            plt.close(fig)

        return {"success": True, "output": output_name, "data": {"size_kb": round(os.path.getsize(svg_path) / 1024, 1)}}
    except Exception as e:
        return {"success": False, "error": f"SVG rendering failed: {e}"}


def _set_height_tag(ent, spec):
    """Store an optional per-entity wall height (metres) as XDATA so it
    survives the DXF round-trip. Key: height | hgt (h is text size)."""
    h = spec.get("height", spec.get("hgt", None))
    if h is None:
        return
    try:
        ent.set_xdata("QCADMCP", [(1040, float(h))])
    except Exception:
        pass


def _ent_height_mm(ent, default_mm):
    """Read per-entity wall height (XDATA, metres) or fall back to default."""
    try:
        if ent.has_xdata("QCADMCP"):
            for tag in ent.get_xdata("QCADMCP"):
                if tag.code == 1040:
                    return float(tag.value) * 1000.0
    except Exception:
        pass
    return default_mm


def _wall_segments(msp, wall_layers, doc, default_h_mm=None):
    """Shared wall detection for extrude/drawings: auto-detect wall layers
    (case-insensitive keyword match), return (segments, used_layers).
    Each segment: {"start": (x, y), "end": (x, y), "h": height_mm} in DXF
    units (mm); per-entity XDATA height wins over the default."""
    wall_keywords = ["wall", "mauer", "wand", "mur", "parete", "pared"]
    if not wall_layers:
        all_layers = {layer.dxf.name.lower() for layer in doc.layers}
        wall_layers = [name for name in all_layers if any(kw in name for kw in wall_keywords)]
        if not wall_layers:
            wall_layers = [layer.dxf.name for layer in doc.layers]

    wall_filter = {w.lower() for w in wall_layers} if wall_layers else set()
    segments = []
    for e in msp:
        if e.get_dxf_attrib("layer", "").lower() not in wall_filter:
            continue
        h = _ent_height_mm(e, default_h_mm) if default_h_mm else None
        if e.dxftype() == "LINE":
            segments.append(
                {"type": "line", "start": (e.dxf.start.x, e.dxf.start.y), "end": (e.dxf.end.x, e.dxf.end.y), "h": h}
            )
        elif e.dxftype() == "LWPOLYLINE":
            pts = [(p[0], p[1]) for p in e.get_points("xy")]
            for i in range(len(pts) - 1):
                segments.append({"type": "line", "start": pts[i], "end": pts[i + 1], "h": h})
            if e.closed and len(pts) > 2:
                segments.append({"type": "line", "start": pts[-1], "end": pts[0], "h": h})
        elif e.dxftype() == "POLYLINE":
            pts = [(p[0], p[1]) for p in e.points()]
            for i in range(len(pts) - 1):
                segments.append({"type": "line", "start": pts[i], "end": pts[i + 1], "h": h})
    return segments, wall_layers


def _drawing_openings(msp):
    """Find door/window markers: INSERT/CIRCLE/ARC/LINE on DOOR/WINDOW/OPENING layers."""
    openings = []
    for e in msp:
        if e.dxftype() not in ("INSERT", "CIRCLE", "ARC", "LINE"):
            continue
        layer_upper = e.get_dxf_attrib("layer", "").upper()
        if "DOOR" in layer_upper:
            kind = "door"
        elif "WINDOW" in layer_upper or "OPENING" in layer_upper:
            kind = "window"
        else:
            continue
        try:
            if e.dxftype() == "INSERT":
                pos = (e.dxf.insert.x, e.dxf.insert.y)
            elif e.dxftype() == "LINE":
                pos = ((e.dxf.start.x + e.dxf.end.x) / 2, (e.dxf.start.y + e.dxf.end.y) / 2)
            else:
                pos = (e.dxf.center.x, e.dxf.center.y)
        except Exception:
            continue
        openings.append({"kind": kind, "x": pos[0], "y": pos[1], "layer": e.get_dxf_attrib("layer", "")})
    return openings


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
    base_elevation: Annotated[
        float, Field(default=0.0, description="Storey base elevation in metres (stacked multilevel builds).")
    ] = 0.0,
) -> dict:
    """
    Extrude walls from a DXF floor plan into a 3D STL mesh.

    Finds LINE and LWPOLYLINE entities on wall layers, extrudes them vertically
    to wall_height with wall_thickness on each side.

    Unit convention: DXF units are millimetres (1 unit = 1 mm, real-world
    scale). wall_height / wall_thickness are given in METRES and converted
    internally (x1000).

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
    height_mm = wall_height * 1000.0
    thick_mm = wall_thickness * 1000.0
    base_mm = base_elevation * 1000.0

    try:
        msp = doc.modelspace()
        wall_segments, _used_layers = _wall_segments(msp, wall_layers, doc, default_h_mm=height_mm)

        if not wall_segments:
            return {
                "success": False,
                "error": "No wall entities found. Try specifying wall_layers or use a DXF with LINE/LWPOLYLINE entities.",
            }

        meshes, heights = _extrude_segments(wall_segments, height_mm, thick_mm, base_mm)
        if not meshes:
            return {"success": False, "error": "Nothing to extrude (all segments degenerate)."}
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
                "base_elevation_m": base_elevation,
                "heights_mm": sorted(heights),
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def _extrude_segments(segments, height_mm, thick_mm, base_mm):
    """Turn wall segments into numpy-stl Mesh boxes. Returns (meshes, heights_mm)."""
    import numpy as np
    from stl.mesh import Mesh

    meshes = []
    heights = set()
    for seg in segments:
        x1, y1 = seg["start"]
        x2, y2 = seg["end"]
        seg_h = seg.get("h") or height_mm
        heights.add(round(seg_h, 1))
        dx, dy = x2 - x1, y2 - y1
        length = np.sqrt(dx * dx + dy * dy)
        if length < 1e-6:
            continue
        nx, ny = -dy / length, dx / length
        hw = thick_mm / 2.0
        z0, z1 = base_mm, base_mm + seg_h
        v = np.array(
            [
                [x1 - nx * hw, y1 - ny * hw, z0],
                [x1 + nx * hw, y1 + ny * hw, z0],
                [x2 + nx * hw, y2 + ny * hw, z0],
                [x2 - nx * hw, y2 - ny * hw, z0],
                [x1 - nx * hw, y1 - ny * hw, z1],
                [x1 + nx * hw, y1 + ny * hw, z1],
                [x2 + nx * hw, y2 + ny * hw, z1],
                [x2 - nx * hw, y2 - ny * hw, z1],
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
    return meshes, heights


async def plan_stack(
    files: Annotated[
        list[dict],
        Field(
            description="Storeys to stack: [{file_name, base_elevation (m, default = 3.5 x index)}]. "
            "Example: [{'file_name': 'tower_L0.dxf', 'base_elevation': 0}, "
            "{'file_name': 'tower_L1.dxf', 'base_elevation': 3.5}]."
        ),
    ],
    output_name: Annotated[str, Field(default="stacked.stl", description="Combined STL filename.")] = "stacked.stl",
    wall_height: Annotated[float, Field(default=3.0, description="Default wall height in metres.")] = 3.0,
    wall_thickness: Annotated[float, Field(default=0.3, description="Wall thickness in metres.")] = 0.3,
    wall_layers: Annotated[
        list[str] | None, Field(default=None, description="Wall layer names. Auto-detected if omitted.")
    ] = None,
) -> dict:
    """
    Stack multiple single-storey DXF plans into one multilevel STL mesh.

    Each file is extruded at its base_elevation (e.g. ground 0 m, L1 3.5 m).
    Per-entity XDATA heights apply within each storey as usual.

    ## Return Format
    {"success": bool, "output": str, "data": {"levels": [...], "wall_count": int, ...}}

    ## Examples
    await plan_stack(files=[{"file_name": "tower_L0.dxf", "base_elevation": 0},
                            {"file_name": "tower_L1.dxf", "base_elevation": 3.5}])
    """
    import numpy as np
    from stl.mesh import Mesh

    stl_path = os.path.join(OUTPUT_DIR, output_name)
    height_mm = wall_height * 1000.0
    thick_mm = wall_thickness * 1000.0

    try:
        all_meshes = []
        heights = set()
        levels_out = []
        total_walls = 0
        for i, spec in enumerate(files):
            fname = spec.get("file_name", "")
            base_mm = float(spec.get("base_elevation", 3.5 * i)) * 1000.0
            doc, err = _load_dxf(fname)
            if doc is None:
                return {"success": False, "error": f"Level {i} ({fname}): {err}"}
            segments, _used = _wall_segments(doc.modelspace(), wall_layers, doc, default_h_mm=height_mm)
            if not segments:
                return {"success": False, "error": f"Level {i} ({fname}): no wall entities found."}
            meshes, lv_heights = _extrude_segments(segments, height_mm, thick_mm, base_mm)
            heights.update(lv_heights)
            all_meshes.extend(meshes)
            total_walls += len(segments)
            levels_out.append({"file": fname, "base_elevation_m": base_mm / 1000.0, "walls": len(segments)})
        if not all_meshes:
            return {"success": False, "error": "Nothing to stack."}
        combined = Mesh(np.concatenate([m.data for m in all_meshes]))
        combined.save(stl_path)
        return {
            "success": True,
            "output": output_name,
            "data": {
                "vertices": len(combined.points),
                "faces": len(combined.data),
                "wall_count": total_walls,
                "levels": levels_out,
                "size_kb": round(os.path.getsize(stl_path) / 1024, 1),
                "heights_mm": sorted(heights),
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def plan_drawings(
    file_name: Annotated[str, Field(description="DXF filename in the depot.")],
    output_prefix: Annotated[str, Field(default="", description="Output filename prefix. Default: DXF stem.")] = "",
    wall_height: Annotated[float, Field(default=3.0, description="Wall height in metres.")] = 3.0,
    wall_thickness: Annotated[float, Field(default=0.3, description="Wall thickness in metres.")] = 0.3,
    wall_layers: Annotated[
        list[str] | None, Field(default=None, description="Wall layer names. Auto-detected if omitted.")
    ] = None,
    views: Annotated[
        str,
        Field(default="elevations,section,iso,roof", description="Comma list: elevations,section,iso,roof."),
    ] = "elevations,section,iso,roof",
    background: Annotated[str, Field(default="white", description="SVG background colour.")] = "white",
) -> dict:
    """
    Generate the full architectural drawing set from a floor plan DXF.

    Derives elevations (N/S/E/W), a cross-section (A-A), an axonometric
    isometric, and a roof plan from the detected wall segments — the standard
    drawings an architect produces beyond the floor plan. Openings (doors /
    windows on DOOR/WINDOW layers) are cut into elevations when present.

    Unit convention: DXF units are millimetres; wall_height in metres.

    ## Return Format
    {"success": bool, "outputs": {"elev_n": ..., ...}, "data": {"wall_count": int, "views": [...], ...}}

    ## Examples
    await plan_drawings(file_name="office.dxf")
    await plan_drawings(file_name="office.dxf", views="elevations,iso")
    """
    import math

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon, Rectangle

    doc, err = _load_dxf(file_name)
    if doc is None:
        return {"success": False, "error": err}

    try:
        msp = doc.modelspace()
        H = wall_height * 1000.0
        T = wall_thickness * 1000.0
        segments, used_layers = _wall_segments(msp, wall_layers, doc, default_h_mm=H)
        if not segments:
            return {
                "success": False,
                "error": "No wall entities found. Try specifying wall_layers or use a DXF with LINE/LWPOLYLINE entities.",
            }
        for s in segments:
            if not s.get("h"):
                s["h"] = H
        Hmax = max(s["h"] for s in segments)
        openings = _drawing_openings(msp)
        xs = [p for s in segments for p in (s["start"][0], s["end"][0])]
        ys = [p for s in segments for p in (s["start"][1], s["end"][1])]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        W, D = x1 - x0, y1 - y0
        prefix = output_prefix or Path(file_name).stem
        want = {v.strip().lower() for v in views.split(",") if v.strip()}

        outputs: dict[str, str] = {}

        def _save(fig, key):
            out_name = f"{prefix}_{key}.svg"
            fig.savefig(os.path.join(OUTPUT_DIR, out_name), format="svg", facecolor=background)
            plt.close(fig)
            outputs[key] = out_name

        def _opening_rects(proj):
            """White opening rects (pos, w, y0, h) projected onto an axis."""
            rects = []
            for o in openings:
                p = o["x"] if proj == "x" else o["y"]
                if o["kind"] == "door":
                    rects.append((p - 450, 0, 900, 2100))
                else:
                    rects.append((p - 600, 900, 1200, 1200))
            return rects

        def _elevation(proj, title, key):
            fig, ax = plt.subplots(figsize=(12, 5))
            span0, span1 = (x0, x1) if proj == "x" else (y0, y1)
            for s in segments:
                a = min(s["start"][0 if proj == "x" else 1], s["end"][0 if proj == "x" else 1])
                b = max(s["start"][0 if proj == "x" else 1], s["end"][0 if proj == "x" else 1])
                sh = s.get("h") or H
                ax.add_patch(Rectangle((a, 0), max(b - a, T * 0.5), sh, facecolor="#e8e8e8", edgecolor="black", lw=1))
            for ox, oy, ow, oh in _opening_rects(proj):
                ax.add_patch(Rectangle((ox, oy), ow, oh, facecolor="white", edgecolor="black", lw=1.2))
            ax.plot([span0, span1], [0, 0], color="black", lw=2.5)
            ax.text(
                (span0 + span1) / 2,
                Hmax * 1.06,
                f"{(span1 - span0) / 1000:.1f} m  |  max height {Hmax / 1000:.1f} m  |  {len(openings)} openings",
                ha="center",
                fontsize=10,
            )
            ax.set_title(title, fontsize=13, fontweight="bold")
            ax.set_aspect("equal")
            ax.margins(0.04)
            ax.axis("off")
            _save(fig, key)

        if "elevations" in want:
            _elevation("x", f"Elevation North — {prefix}", "elev_n")
            _elevation("x", f"Elevation South — {prefix}", "elev_s")
            _elevation("y", f"Elevation East — {prefix}", "elev_e")
            _elevation("y", f"Elevation West — {prefix}", "elev_w")

        if "section" in want:
            fig, ax = plt.subplots(figsize=(12, 5))
            cut = (y0 + y1) / 2
            for s in segments:
                (sx1, sy1), (sx2, sy2) = s["start"], s["end"]
                if min(sy1, sy2) - T <= cut <= max(sy1, sy2) + T:
                    a, b = min(sx1, sx2), max(sx1, sx2)
                    sh = s.get("h") or H
                    ax.add_patch(
                        Rectangle((a, 0), max(b - a, T * 0.5), sh, facecolor="#e8e8e8", edgecolor="black", lw=1)
                    )
            ax.plot([x0, x1], [0, 0], color="black", lw=2.5)  # ground slab
            ax.plot([x0, x1], [Hmax, Hmax], color="black", lw=1.5)  # ceiling slab
            for gx in [x0 + i * max(W / 40, T) for i in range(int(W / max(W / 40, T)) + 1)]:
                ax.plot([gx, gx - T * 0.4], [0, -T * 0.4], color="black", lw=0.8)  # ground hatch
            ax.text(
                (x0 + x1) / 2,
                Hmax * 1.06,
                f"Section A-A (cut at y={(cut - y0) / 1000:.1f} m)  |  {W / 1000:.1f} m span",
                ha="center",
                fontsize=10,
            )
            ax.set_title(f"Section A-A — {prefix}", fontsize=13, fontweight="bold")
            ax.set_aspect("equal")
            ax.margins(0.04)
            ax.axis("off")
            _save(fig, "section_aa")

        if "iso" in want:
            fig, ax = plt.subplots(figsize=(10, 8))
            c30, s30 = math.cos(math.radians(30)), math.sin(math.radians(30))

            def _proj(x, y, z):
                return ((x - y) * c30, (x + y) * s30 - z)

            for s in segments:
                (sx1, sy1), (sx2, sy2) = s["start"], s["end"]
                sh = s.get("h") or H
                dx, dy = sx2 - sx1, sy2 - sy1
                length = math.hypot(dx, dy)
                if length < 1e-6:
                    continue
                nx, ny = -dy / length, dx / length
                hw = T / 2.0
                corners = [
                    (sx1 - nx * hw, sy1 - ny * hw, 0),
                    (sx1 + nx * hw, sy1 + ny * hw, 0),
                    (sx2 + nx * hw, sy2 + ny * hw, 0),
                    (sx2 - nx * hw, sy2 - ny * hw, 0),
                    (sx1 - nx * hw, sy1 - ny * hw, sh),
                    (sx1 + nx * hw, sy1 + ny * hw, sh),
                    (sx2 + nx * hw, sy2 + ny * hw, sh),
                    (sx2 - nx * hw, sy2 - ny * hw, sh),
                ]
                p = [_proj(*c) for c in corners]
                ax.add_patch(Polygon([p[4], p[5], p[6], p[7]], fc="#dedede", ec="black", lw=0.8))  # top
                ax.add_patch(Polygon([p[0], p[1], p[5], p[4]], fc="#bdbdbd", ec="black", lw=0.8))  # side A
                ax.add_patch(Polygon([p[1], p[2], p[6], p[5]], fc="#9a9a9a", ec="black", lw=0.8))  # side B
            g = [_proj(x, y, 0) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
            ax.add_patch(Polygon(g, fc="none", ec="black", lw=1.5))
            ax.text(
                sum(p[0] for p in g) / 4,
                max(p[1] for p in g) * 1.02,
                f"Axonometric  |  {W / 1000:.1f} x {D / 1000:.1f} x {Hmax / 1000:.1f} m (max)",
                ha="center",
                fontsize=10,
            )
            ax.set_title(f"Isometric — {prefix}", fontsize=13, fontweight="bold")
            ax.set_aspect("equal")
            ax.margins(0.06)
            ax.axis("off")
            _save(fig, "iso")

        if "roof" in want:
            fig, ax = plt.subplots(figsize=(10, 8))
            ax.add_patch(Rectangle((x0, y0), W, D, fc="none", ec="black", lw=2))
            inset = 300.0
            if W > inset * 2 and D > inset * 2:
                ax.add_patch(
                    Rectangle((x0 + inset, y0 + inset), W - inset * 2, D - inset * 2, fc="#f0f0f0", ec="black", lw=1)
                )
            ax.plot([x0, x1], [(y0 + y1) / 2, (y0 + y1) / 2], color="black", lw=1, ls="--")  # ridge
            ax.text(
                (x0 + x1) / 2,
                y1 + D * 0.04,
                f"Roof plan (flat, parapet 300)  |  {W / 1000:.1f} x {D / 1000:.1f} m",
                ha="center",
                fontsize=10,
            )
            ax.set_title(f"Roof plan — {prefix}", fontsize=13, fontweight="bold")
            ax.set_aspect("equal")
            ax.margins(0.06)
            ax.axis("off")
            _save(fig, "roof")

        return {
            "success": True,
            "outputs": outputs,
            "data": {
                "views": sorted(outputs.keys()),
                "wall_count": len(segments),
                "wall_layers": used_layers,
                "bbox_mm": {"x0": x0, "x1": x1, "y0": y0, "y1": y1},
                "height_mm": Hmax,
                "heights_mm": sorted({round(s.get("h") or H, 1) for s in segments}),
                "openings": len(openings),
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

    Supported entity types (lenient key aliases accepted — the webapp Demo page
    sends x1/y1/x2/y2 shapes, MCP clients may send x/y/w/h):
    - line:   {"type": "line", "x1": 0, "y1": 0, "x2": 100, "y2": 0, "layer": "walls"}
    - rect:   {"type": "rect", "x": 10, "y": 10, "w": 80, "h": 60, "layer": "rooms"}
      alias:  {"type": "rect", "x1": 10, "y1": 10, "x2": 90, "y2": 70, "layer": "rooms"}
    - circle: {"type": "circle", "cx": 50, "cy": 50, "r": 20, "layer": "columns"}
      alias:  {"type": "circle", "x": 50, "y": 50, "r": 20, "layer": "columns"}
    - text:   {"type": "text", "x": 50, "y": 50, "content": "Label", "height": 5, "layer": "labels"}
      alias:  {"type": "text", "x": 50, "y": 50, "text": "Label", "h": 5, "layer": "labels"}
    - polyline: {"type": "polyline", "points": [[0,0], [100,0], [100,50], [0,50]], "closed": true, "layer": "walls"}
    - arc:   {"type": "arc", "cx": 50, "cy": 50, "r": 20, "start_angle": 0, "end_angle": 90, "layer": "doors"}
    - door:  {"type": "door", "x": 10, "y": 10, "w": 900, "angle": 0, "swing": 90, "layer": "Doors"}
      (leaf line + swing arc; detected as an opening by plan_drawings)
    - window: {"type": "window", "x1": 10, "y1": 0, "x2": 1600, "y2": 0, "layer": "Windows"}
      (triple-line sill symbol; detected as an opening by plan_drawings)

    Any line/rect/circle/polyline/arc entity accepts an optional "hgt"
    (or "height") in METRES for per-entity wall height, stored as XDATA and
    honoured by plan_extrude / plan_drawings (e.g. nave 12, towers 25).
    Without it the tool default height applies.

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
        if "QCADMCP" not in doc.appids:
            doc.appids.add("QCADMCP")

        # Draw entities
        count = 0
        for ent in entities:
            etype = ent.get("type", "")
            layer = ent.get("layer", "0")
            try:
                if etype == "line":
                    _set_height_tag(
                        msp.add_line((ent["x1"], ent["y1"]), (ent["x2"], ent["y2"]), dxfattribs={"layer": layer}),
                        ent,
                    )
                    count += 1
                elif etype == "rect":
                    if "x1" in ent and "x2" in ent:
                        # Corner-shape (webapp Demo page): normalise to x/y/w/h.
                        x0, x1 = sorted([ent["x1"], ent["x2"]])
                        y0, y1 = sorted([ent["y1"], ent["y2"]])
                        x, y, w, h = x0, y0, x1 - x0, y1 - y0
                    else:
                        x, y, w, h = ent["x"], ent["y"], ent["w"], ent["h"]
                    _set_height_tag(
                        msp.add_lwpolyline(
                            [(x, y), (x + w, y), (x + w, y + h), (x, y + h)],
                            close=True,
                            dxfattribs={"layer": layer},
                        ),
                        ent,
                    )
                    count += 1
                elif etype == "circle":
                    cx = ent.get("cx", ent.get("x"))
                    cy = ent.get("cy", ent.get("y"))
                    _set_height_tag(msp.add_circle((cx, cy), ent["r"], dxfattribs={"layer": layer}), ent)
                    count += 1
                elif etype == "text":
                    content = ent.get("content", ent.get("text", ""))
                    height = ent.get("height", ent.get("h", 2.5))
                    t = msp.add_text(content, dxfattribs={"layer": layer})
                    # Direct attrib writes (ezdxf 1.x dropped Text.set_pos).
                    t.dxf.insert = (ent["x"], ent["y"])
                    t.dxf.height = height
                    count += 1
                elif etype == "polyline":
                    pts = [Vec2(p[0], p[1]) for p in ent.get("points", [])]
                    if len(pts) >= 2:
                        _set_height_tag(
                            msp.add_lwpolyline(pts, close=ent.get("closed", False), dxfattribs={"layer": layer}),
                            ent,
                        )
                        count += 1
                elif etype == "arc":
                    cx = ent.get("cx", ent.get("x", 0))
                    cy = ent.get("cy", ent.get("y", 0))
                    _set_height_tag(
                        msp.add_arc(
                            (cx, cy),
                            ent["r"],
                            float(ent.get("start_angle", 0)),
                            float(ent.get("end_angle", 90)),
                            dxfattribs={"layer": layer},
                        ),
                        ent,
                    )
                    count += 1
                elif etype == "door":
                    # Door leaf + swing arc on the Doors layer (picked up as an
                    # opening by plan_drawings / plan_to_ifc_data).
                    import math as _math

                    hx, hy = ent["x"], ent["y"]
                    w = ent.get("w", 900)
                    ang = _math.radians(ent.get("angle", 0))
                    swing = ent.get("swing", 90)
                    dx, dy = _math.cos(ang), _math.sin(ang)
                    msp.add_line((hx, hy), (hx + dx * w, hy + dy * w), dxfattribs={"layer": layer})
                    msp.add_arc(
                        (hx, hy), w, ent.get("angle", 0), ent.get("angle", 0) + swing, dxfattribs={"layer": layer}
                    )
                    count += 2
                elif etype == "window":
                    # Triple-line sill symbol on the Windows layer.
                    import math as _math

                    (wx1, wy1), (wx2, wy2) = (ent["x1"], ent["y1"]), (ent["x2"], ent["y2"])
                    dx, dy = wx2 - wx1, wy2 - wy1
                    length = _math.hypot(dx, dy) or 1.0
                    nx, ny = -dy / length, dx / length
                    for off in (-150.0, 0.0, 150.0):
                        msp.add_line(
                            (wx1 + nx * off, wy1 + ny * off),
                            (wx2 + nx * off, wy2 + ny * off),
                            dxfattribs={"layer": layer},
                        )
                    count += 3
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
    mcp.tool(annotations=_MUTATING, version="0.3.0")(plan_stack)
    mcp.tool(annotations=_MUTATING, version="0.3.0")(plan_drawings)
    mcp.tool(annotations=_MUTATING, version="0.3.0")(plan_export)
    mcp.tool(annotations=_README_ONLY, version="0.3.0")(plan_analyse)
    mcp.tool(annotations=_MUTATING, version="0.3.0")(plan_create)
    mcp.tool(annotations=_README_ONLY, version="0.3.0")(plan_depot)
