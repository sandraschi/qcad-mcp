"""Portmanteau tool surface for QCAD MCP (v0.5.0).

[RATIONALE] Consolidates 42 discrete MCP tools into 8 domain portmanteaus
(plan, plan_edit, plan_annotate, plan_pro, plan_library, plan_ai, plan_bim,
qcad) plus 4 Prefab display cards. Each portmanteau takes an ``op`` Literal
discriminator plus the union of its ops' parameters; unneeded params are
ignored per-op. The original per-op coroutines stay importable in their
modules (tests and server internals use them); only MCP/REST registration
moves here, so the LLM tool list drops from 42 to 12.

Op names are the old tool names minus the ``plan_``/``qcad_`` prefix
(e.g. ``plan_info`` -> ``plan(op="info", ...)``).
"""

from typing import Annotated, Any, Literal

from fastmcp import Context
from pydantic import Field

from qcad_mcp.tools import agentic_tools as _ag
from qcad_mcp.tools import annotation_tools as _an
from qcad_mcp.tools import bim_tools as _bim
from qcad_mcp.tools import block_tools as _bl
from qcad_mcp.tools import core_tools as _core
from qcad_mcp.tools import meta_tools as _meta
from qcad_mcp.tools import modify_tools as _mod
from qcad_mcp.tools import qcad_tools as _pro
from qcad_mcp.tools import script_tools as _sc

_M = {}  # mutating-or-mixed tool annotation
_R = {"readonly": True}

CoreOp = Literal["info", "to_svg", "extrude", "stack", "obj", "glb", "drawings", "export", "analyse", "create", "depot"]
EditOp = Literal["convert", "modify"]
AnnotateOp = Literal["dimension", "measure", "text", "hatch", "block_insert", "array", "wall_data", "beam_analysis"]
ProOp = Literal["script", "render", "exec"]
LibraryOp = Literal["blocks", "blocks_download", "scripts_search", "scripts_download"]
AiOp = Literal["generate", "agentic", "transpile", "sampling"]
BimOp = Literal["auto_dimension", "building_meta", "to_ifc_data"]
MetaOp = Literal["status", "help", "shutdown"]


def _need(**kwargs: Any) -> dict | None:
    """Return an error dict when any named required param is empty, else None."""
    missing = [k for k, v in kwargs.items() if v is None or v == "" or v == [] or v == {}]
    if missing:
        return {"success": False, "error": f"Missing required parameters for this op: {', '.join(missing)}"}
    return None


async def plan(
    op: Annotated[
        CoreOp,
        Field(
            description="Core operation: info, to_svg, extrude, stack, obj, glb, drawings, export, analyse, create, depot."
        ),
    ],
    file_name: Annotated[str, Field(default="", description="DXF filename in the depot (most ops).")] = "",
    filename: Annotated[str, Field(default="", description="Output filename for create (must end in .dxf).")] = "",
    output_name: Annotated[str, Field(default="", description="Output filename. Auto-generated if empty.")] = "",
    entities: Annotated[
        list[dict] | None,
        Field(default=None, description="Entity dicts for create: line, rect, circle, text, polyline."),
    ] = None,
    layers: Annotated[list[dict] | None, Field(default=None, description="Layer definitions for create.")] = None,
    description: Annotated[str, Field(default="", description="Description stored in depot metadata (create).")] = "",
    files: Annotated[
        list[dict] | None, Field(default=None, description="Storeys to stack: [{file_name, base_elevation}].")
    ] = None,
    wall_height: Annotated[float, Field(default=3.0, description="Wall extrusion height in metres.")] = 3.0,
    wall_thickness: Annotated[float, Field(default=0.3, description="Wall thickness in metres.")] = 0.3,
    wall_layers: Annotated[
        list[str] | None, Field(default=None, description="Wall layer names. Auto-detected if omitted.")
    ] = None,
    base_elevation: Annotated[float, Field(default=0.0, description="Storey base elevation in metres.")] = 0.0,
    slab: Annotated[bool, Field(default=True, description="Add a floor slab under the walls.")] = True,
    slab_thickness: Annotated[float, Field(default=0.25, description="Slab thickness in metres.")] = 0.25,
    textured: Annotated[bool, Field(default=True, description="Emit procedural textures (obj).")] = True,
    green_roof: Annotated[bool, Field(default=False, description="Grass material on the slab.")] = False,
    obj_name: Annotated[str, Field(default="", description="Existing OBJ in outputs to convert (glb).")] = "",
    views: Annotated[
        str, Field(default="elevations,section,iso,roof", description="Drawing-set views (drawings).")
    ] = "elevations,section,iso,roof",
    background: Annotated[str, Field(default="white", description="SVG background colour.")] = "white",
    svg_layers: Annotated[
        list[str] | None, Field(default=None, description="Layer names to include (to_svg). All layers if omitted.")
    ] = None,
    format: Annotated[str, Field(default="svg", description="Output format for export: svg, pdf, or png.")] = "svg",
) -> dict:
    """Core ezdxf operations: inspect, preview, extrude, convert, analyse, and create DXF files.

    No QCAD Pro needed for any op in this tool.

    ## Return Format
    {"success": bool, ...op-specific data (output, data, error)}

    ## Examples
    await plan(op="info", file_name="floorplan.dxf")
    await plan(op="to_svg", file_name="floorplan.dxf")
    await plan(op="extrude", file_name="floorplan.dxf", wall_height=3.0)
    await plan(op="create", filename="room.dxf", entities=[{"type": "rect", "x": 0, "y": 0, "w": 5000, "h": 4000}])
    await plan(op="depot")
    """
    if op == "info":
        if (err := _need(file_name=file_name)) is not None:
            return err
        return await _core.plan_info(file_name=file_name)
    if op == "to_svg":
        if (err := _need(file_name=file_name)) is not None:
            return err
        return await _core.plan_to_svg(
            file_name=file_name, output_name=output_name or "output.svg", layers=svg_layers, background=background
        )
    if op == "extrude":
        if (err := _need(file_name=file_name)) is not None:
            return err
        return await _core.plan_extrude(
            file_name=file_name,
            output_name=output_name or "extruded.stl",
            wall_height=wall_height,
            wall_thickness=wall_thickness,
            wall_layers=wall_layers,
            base_elevation=base_elevation,
            slab=slab,
            slab_thickness=slab_thickness,
        )
    if op == "stack":
        if (err := _need(files=files)) is not None:
            return err
        assert files is not None
        return await _core.plan_stack(
            files=files,
            output_name=output_name or "stacked.stl",
            wall_height=wall_height,
            wall_thickness=wall_thickness,
            wall_layers=wall_layers,
            slab=slab,
            slab_thickness=slab_thickness,
        )
    if op == "obj":
        if (err := _need(file_name=file_name)) is not None:
            return err
        return await _core.plan_obj(
            file_name=file_name,
            output_name=output_name,
            wall_height=wall_height,
            wall_thickness=wall_thickness,
            wall_layers=wall_layers,
            base_elevation=base_elevation,
            textured=textured,
            slab=slab,
            slab_thickness=slab_thickness,
            green_roof=green_roof,
        )
    if op == "glb":
        return await _core.plan_glb(
            file_name=file_name,
            obj_name=obj_name,
            output_name=output_name,
            wall_height=wall_height,
            wall_thickness=wall_thickness,
            wall_layers=wall_layers,
            green_roof=green_roof,
        )
    if op == "drawings":
        if (err := _need(file_name=file_name)) is not None:
            return err
        return await _core.plan_drawings(
            file_name=file_name,
            output_prefix=output_name,
            wall_height=wall_height,
            wall_thickness=wall_thickness,
            wall_layers=wall_layers,
            views=views,
            background=background,
        )
    if op == "export":
        if (err := _need(file_name=file_name)) is not None:
            return err
        return await _core.plan_export(file_name=file_name, format=format, output_name=output_name)
    if op == "analyse":
        if (err := _need(file_name=file_name)) is not None:
            return err
        return await _core.plan_analyse(file_name=file_name)
    if op == "create":
        if (err := _need(filename=filename, entities=entities)) is not None:
            return err
        assert entities is not None
        return await _core.plan_create(filename=filename, entities=entities, layers=layers, description=description)
    if op == "depot":
        return await _core.plan_depot()
    return {"success": False, "error": f"Unknown core op: {op}"}


async def plan_edit(
    op: Annotated[
        EditOp, Field(description="Edit operation: convert (DWG<->DXF via QCAD Pro) or modify (layers/entities).")
    ],
    file_name: Annotated[str, Field(default="", description="DWG or DXF filename in the depot.")] = "",
    output_name: Annotated[
        str, Field(default="", description="Output filename. Required for convert (must end in .dxf or .dwg).")
    ] = "",
    operations: Annotated[
        list[dict] | None,
        Field(default=None, description="Modification operations for modify (delete, offset, layer-*, merge-layers)."),
    ] = None,
) -> dict:
    """Convert between DWG/DXF and modify layers/entities in place.

    ## Return Format
    {"success": bool, "output": str, "data": {...}}

    ## Examples
    await plan_edit(op="convert", file_name="plan.dwg", output_name="plan.dxf")
    await plan_edit(op="modify", file_name="plan.dxf", operations=[{"op": "layer-freeze", "layer_filter": "Furniture"}])
    """
    if op == "convert":
        if (err := _need(file_name=file_name, output_name=output_name)) is not None:
            return err
        return await _mod.plan_convert(file_name=file_name, output_name=output_name)
    if op == "modify":
        if (err := _need(file_name=file_name, operations=operations)) is not None:
            return err
        assert operations is not None
        return await _mod.plan_modify(file_name=file_name, operations=operations)
    return {"success": False, "error": f"Unknown edit op: {op}"}


async def plan_annotate(
    op: Annotated[
        AnnotateOp,
        Field(
            description="Annotation operation: dimension, measure, text, hatch, block_insert, array, wall_data, beam_analysis."
        ),
    ],
    file_name: Annotated[str, Field(default="", description="DXF/DWG filename in the depot.")] = "",
    output_name: Annotated[str, Field(default="", description="Output filename. Auto-generated if empty.")] = "",
    dimensions: Annotated[
        list[dict] | None,
        Field(default=None, description="Dimension specs (aligned, rotated, radial, diametric, angular)."),
    ] = None,
    texts: Annotated[
        list[dict] | None, Field(default=None, description="Text annotations: text, x, y, height, layer, rotation.")
    ] = None,
    hatches: Annotated[
        list[dict] | None, Field(default=None, description="Hatch specs: points, pattern, scale, angle, layer.")
    ] = None,
    inserts: Annotated[
        list[dict] | None, Field(default=None, description="Block insertions: block_name, x, y, scale, rotation.")
    ] = None,
    pattern: Annotated[str, Field(default="", description="Array type: rectangular or polar.")] = "",
    count: Annotated[int, Field(default=0, description="Number of array copies (including the original).")] = 0,
    params: Annotated[dict | None, Field(default=None, description="Array parameters: dx/dy or cx/cy/angle.")] = None,
    wall_layers: Annotated[
        str, Field(default="", description="Comma-separated wall layers (wall_data). Empty = auto-detect.")
    ] = "",
    wall_thickness: Annotated[
        float, Field(default=0.3, description="Default wall thickness in metres (wall_data).")
    ] = 0.3,
    beams: Annotated[
        list[dict] | None, Field(default=None, description="Beam segments for FEA: x1,y1,x2,y2,height,width,E.")
    ] = None,
    supports: Annotated[list[dict] | None, Field(default=None, description="FEA supports. Empty = auto.")] = None,
    loads: Annotated[list[dict] | None, Field(default=None, description="FEA loads. Empty = auto.")] = None,
) -> dict:
    """Dimensions, text, hatches, blocks, arrays, wall BIM data, and beam FEA.

    measure/wall_data/beam_analysis are read-only; the rest write a new DXF.
    QCAD Pro is used when available, ezdxf fallback otherwise.

    ## Return Format
    {"success": bool, "output": str, "data": {...}}

    ## Examples
    await plan_annotate(op="measure", file_name="floorplan.dxf")
    await plan_annotate(op="text", file_name="floorplan.dxf", texts=[{"text": "Kitchen", "x": 1000, "y": 2000, "height": 250}])
    await plan_annotate(op="beam_analysis", beams=[{"x1": 0, "y1": 0, "x2": 5000, "y2": 0}])
    """
    if op == "dimension":
        if (err := _need(file_name=file_name, dimensions=dimensions)) is not None:
            return err
        assert dimensions is not None
        return await _an.plan_dimension(file_name=file_name, dimensions=dimensions, output_name=output_name)
    if op == "measure":
        if (err := _need(file_name=file_name)) is not None:
            return err
        return await _an.plan_measure(file_name=file_name)
    if op == "text":
        if (err := _need(file_name=file_name, texts=texts)) is not None:
            return err
        assert texts is not None
        return await _an.plan_text(file_name=file_name, texts=texts, output_name=output_name)
    if op == "hatch":
        if (err := _need(file_name=file_name, hatches=hatches)) is not None:
            return err
        assert hatches is not None
        return await _an.plan_hatch(file_name=file_name, hatches=hatches, output_name=output_name)
    if op == "block_insert":
        if (err := _need(file_name=file_name, inserts=inserts)) is not None:
            return err
        assert inserts is not None
        return await _an.plan_block_insert(file_name=file_name, inserts=inserts, output_name=output_name)
    if op == "array":
        if (err := _need(file_name=file_name, pattern=pattern)) is not None:
            return err
        if count <= 0:
            return {"success": False, "error": "Missing required parameters for this op: count (must be >= 1)"}
        return await _an.plan_array(
            file_name=file_name, pattern=pattern, count=count, params=params or {}, output_name=output_name
        )
    if op == "wall_data":
        if (err := _need(file_name=file_name)) is not None:
            return err
        return await _an.plan_wall_data(file_name=file_name, wall_layers=wall_layers, wall_thickness=wall_thickness)
    if op == "beam_analysis":
        if (err := _need(beams=beams)) is not None:
            return err
        assert beams is not None
        return await _an.plan_beam_analysis(beams=beams, supports=supports or [], loads=loads or [])
    return {"success": False, "error": f"Unknown annotate op: {op}"}


async def plan_pro(
    op: Annotated[
        ProOp,
        Field(description="QCAD Pro operation: script (full ECMAScript), render (hi-fi export), exec (quick snippet)."),
    ],
    code: Annotated[str, Field(default="", description="ECMAScript code (script) or snippet (exec).")] = "",
    file_name: Annotated[str, Field(default="", description="DXF/DWG filename in the depot.")] = "",
    format: Annotated[str, Field(default="svg", description="Output format for render: svg, pdf, or bmp.")] = "svg",
    output_name: Annotated[
        str | None, Field(default=None, description="Output filename. Defaults per op (script: script_output.dxf).")
    ] = None,
) -> dict:
    """Execute ECMAScript in QCAD Pro and render publication-quality output.

    Requires a QCAD Pro install (check qcad(op="status") first).

    ## Return Format
    {"success": bool, "output": str, "data": {...}}

    ## Examples
    await plan_pro(op="exec", code="print(transientEntityCount());")
    await plan_pro(op="render", file_name="floorplan.dxf", output_name="proof.pdf")
    """
    if op == "script":
        if (err := _need(code=code)) is not None:
            return err
        return await _pro.plan_script(
            code=code, file_name=file_name, output_name=output_name if output_name is not None else "script_output.dxf"
        )
    if op == "render":
        if (err := _need(file_name=file_name)) is not None:
            return err
        return await _pro.plan_render(file_name=file_name, format=format, output_name=output_name or "")
    if op == "exec":
        if (err := _need(code=code)) is not None:
            return err
        return await _pro.plan_exec(code=code, file_name=file_name)
    return {"success": False, "error": f"Unknown pro op: {op}"}


async def plan_library(
    op: Annotated[
        LibraryOp, Field(description="Library operation: blocks, blocks_download, scripts_search, scripts_download.")
    ],
    query: Annotated[str, Field(default="", description="Search term (empty = browse).")] = "",
    category: Annotated[str, Field(default="", description="Category filter.")] = "",
    source: Annotated[
        str, Field(default="all", description="Source: gallery, gist, examples, cadblocksfree, biblocad, or all.")
    ] = "all",
    limit: Annotated[int, Field(default=20, description="Max results.")] = 20,
    title: Annotated[str, Field(default="", description="Item title for downloads (used as filename).")] = "",
    url: Annotated[
        str, Field(default="", description="Download URL (blocks_download) or gallery://id (scripts_download).")
    ] = "",
) -> dict:
    """Search 4800+ CAD blocks and the QCAD script gallery; download to the depot.

    ## Return Format
    {"success": bool, "data": {"results": [...]}, "output": str}

    ## Examples
    await plan_library(op="blocks", query="door", category="doors-windows")
    await plan_library(op="scripts_search", query="hatch")
    """
    if op == "blocks":
        return await _bl.plan_blocks(query=query, category=category, source=source, limit=limit)
    if op == "blocks_download":
        if (err := _need(title=title, source=source, url=url)) is not None:
            return err
        return await _bl.plan_blocks_download(title=title, source=source, url=url)
    if op == "scripts_search":
        return await _sc.plan_scripts_search(query=query, category=category, source=source, limit=limit)
    if op == "scripts_download":
        if (err := _need(title=title, source=source)) is not None:
            return err
        return await _sc.plan_scripts_download(title=title, source=source, url=url)
    return {"success": False, "error": f"Unknown library op: {op}"}


async def plan_ai(
    op: Annotated[
        AiOp,
        Field(
            description="AI operation: generate (NL floor plan), agentic (NL workflow), transpile (AutoLISP), sampling (host LLM reason)."
        ),
    ],
    goal: Annotated[str, Field(default="", description="Natural-language goal or question.")] = "",
    filename: Annotated[
        str, Field(default="", description="Output DXF name (generate). Empty = slug from the goal.")
    ] = "",
    model: Annotated[str, Field(default="", description="Ollama model override (generate fallback).")] = "",
    create_dxf: Annotated[bool, Field(default=True, description="Create depot DXF file(s) (generate).")] = True,
    file_name: Annotated[str, Field(default="", description="Optional depot file to work on (agentic).")] = "",
    lisp_code: Annotated[str, Field(default="", description="AutoLISP source to translate (transpile).")] = "",
    output_name: Annotated[str | None, Field(default=None, description="Output filename (transpile).")] = None,
    ctx: Context | None = None,
) -> dict:
    """Natural-language CAD: generate plans, run agentic workflows, transpile AutoLISP.

    ## Return Format
    {"success": bool, "output": str, "data": {...}, "sampling_used": bool}

    ## Examples
    await plan_ai(op="generate", goal="L-shaped pottery workshop 12m x 9m with a darkroom")
    await plan_ai(op="sampling", goal="What wall height suits a residential floor plan?")
    await plan_ai(op="transpile", lisp_code="(command \\"_.LINE\\" '(0 0) '(100 0) \\"\\")")
    """
    if op == "generate":
        if (err := _need(goal=goal)) is not None:
            return err
        return await _ag.plan_generate(goal=goal, filename=filename, model=model, create_dxf=create_dxf, ctx=ctx)
    if op == "agentic":
        if (err := _need(goal=goal)) is not None:
            return err
        return await _ag.plan_agentic(goal=goal, file_name=file_name, ctx=ctx)
    if op == "transpile":
        if (err := _need(lisp_code=lisp_code)) is not None:
            return err
        return await _ag.plan_transpile(
            lisp_code=lisp_code, output_name=output_name or "transpiled_output.dxf", ctx=ctx
        )
    if op == "sampling":
        if (err := _need(goal=goal)) is not None:
            return err
        return await _ag.cad_sampling(goal=goal, ctx=ctx)
    return {"success": False, "error": f"Unknown ai op: {op}"}


async def plan_bim(
    op: Annotated[BimOp, Field(description="BIM operation: auto_dimension, building_meta, to_ifc_data.")],
    file_name: Annotated[str, Field(default="", description="DXF filename in depot.")] = "",
    wall_layers: Annotated[list[str] | None, Field(default=None, description="Wall layer names.")] = None,
    offset: Annotated[float, Field(default=500.0, description="Dimension line offset (auto_dimension).")] = 500.0,
    output_name: Annotated[str | None, Field(default=None, description="Optional output DXF (auto_dimension).")] = None,
    level_name: Annotated[str | None, Field(default=None, description="Level filter (building_meta).")] = None,
    elevation: Annotated[float | None, Field(default=None, description="Base elevation (building_meta).")] = None,
    wall_height: Annotated[float, Field(default=3000.0, description="Wall height in mm (to_ifc_data).")] = 3000.0,
    wall_thickness: Annotated[float, Field(default=200.0, description="Wall thickness in mm (to_ifc_data).")] = 200.0,
) -> dict:
    """BIM handoff helpers: auto-dimension walls, storey metadata, IFC-shaped JSON.

    ## Return Format
    {"success": bool, "output": str, "data": {...}}

    ## Examples
    await plan_bim(op="building_meta", file_name="tower_L0.dxf")
    await plan_bim(op="auto_dimension", file_name="floorplan.dxf", offset=400.0)
    """
    if op == "auto_dimension":
        if (err := _need(file_name=file_name)) is not None:
            return err
        return await _bim.plan_auto_dimension(
            file_name=file_name, wall_layers=wall_layers, offset=offset, output_name=output_name
        )
    if op == "building_meta":
        if (err := _need(file_name=file_name)) is not None:
            return err
        return await _bim.plan_building_meta(file_name=file_name, level_name=level_name, elevation=elevation)
    if op == "to_ifc_data":
        if (err := _need(file_name=file_name)) is not None:
            return err
        return await _bim.plan_to_ifc_data(
            file_name=file_name, wall_layers=wall_layers, wall_height=wall_height, wall_thickness=wall_thickness
        )
    return {"success": False, "error": f"Unknown bim op: {op}"}


async def qcad(
    op: Annotated[
        MetaOp,
        Field(description="Server operation: status (QCAD Pro install), help (tool catalog), shutdown (orderly exit)."),
    ],
    topic: Annotated[str, Field(default="", description="Filter tools by substring (help).")] = "",
    confirm: Annotated[bool, Field(default=False, description="Must be true for shutdown.")] = False,
) -> dict:
    """QCAD server itself: install status, live help catalog, orderly shutdown.

    ## Return Format
    {"success": bool, "message": str, "data": {...}}

    ## Examples
    await qcad(op="status")
    await qcad(op="help", topic="extrude")
    await qcad(op="shutdown", confirm=True)
    """
    if op == "status":
        return await _pro.qcad_status()
    if op == "help":
        return await _meta.qcad_help(topic=topic)
    if op == "shutdown":
        return await _meta.qcad_shutdown(confirm=confirm)
    return {"success": False, "error": f"Unknown qcad op: {op}"}


def register(mcp) -> None:
    """Register the 8 portmanteau tools (v0.4.0 surface)."""
    mcp.tool(annotations=_M, version="0.5.0")(plan)
    mcp.tool(annotations=_M, version="0.5.0")(plan_edit)
    mcp.tool(annotations=_M, version="0.5.0")(plan_annotate)
    mcp.tool(annotations=_M, version="0.5.0")(plan_pro)
    mcp.tool(annotations=_M, version="0.5.0")(plan_library)
    mcp.tool(annotations=_M, version="0.5.0")(plan_ai)
    mcp.tool(annotations=_M, version="0.5.0")(plan_bim)
    mcp.tool(annotations=_R, version="0.5.0")(qcad)
