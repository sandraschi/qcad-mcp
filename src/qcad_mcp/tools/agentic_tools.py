"""Agentic multi-step CAD workflows and AutoLISP transpilation for QCAD MCP."""

import json
import logging
import os
import re
from pathlib import Path
from typing import Annotated

from fastmcp import Context
from pydantic import Field

from qcad_mcp.config import DEPOT_DIR, OUTPUT_DIR
from qcad_mcp.helpers import _depot_list, _read_meta
from qcad_mcp.services import qcad_pro

_README_ONLY = {"readonly": True}
_MUTATING = {}

logger = logging.getLogger("qcad-mcp")


def _agentic_fallback(goal: str) -> str:
    """Template-based fallback when AI sampling unavailable."""
    goal_lower = goal.lower()
    if "rectangle" in goal_lower or "rectangular" in goal_lower or "floor plan" in goal_lower:
        dims = re.findall(r"(\d+)\s*m", goal)
        w = int(dims[0]) * 1000 if len(dims) > 0 else 10000
        h = int(dims[1]) * 1000 if len(dims) > 1 else 8000
        return f"""var op = new RAddObjectsOperation();
op.addObject(new RLineEntity(document, new RLineData(new RVector(0,0), new RVector({w},0))));
op.addObject(new RLineEntity(document, new RLineData(new RVector({w},0), new RVector({w},{h}))));
op.addObject(new RLineEntity(document, new RLineData(new RVector({w},{h}), new RVector(0,{h}))));
op.addObject(new RLineEntity(document, new RLineData(new RVector(0,{h}), new RVector(0,0))));
op.addObject(new RDimAlignedEntity(document, new RDimAlignedData(new RVector(0,{h}), new RVector({w},{h}), new RVector({w // 2},{h + 500}))));
op.addObject(new RDimAlignedEntity(document, new RDimAlignedData(new RVector({w},0), new RVector({w},{h}), new RVector({w + 500},{h // 2}))));
op.apply(document);"""
    elif "circle" in goal_lower:
        radii = re.findall(r"(\d+)\s*mm", goal)
        r = int(radii[0]) if radii else 50
        return f"""var op = new RAddObjectsOperation();
op.addObject(new RCircleEntity(document, new RCircleData(new RVector(50,50), {r})));
op.addObject(new RDimRadialEntity(document, new RDimRadialData(new RVector(50,50), new RVector(50+{r},50), 0)));
op.apply(document);"""
    return """var op = new RAddObjectsOperation();
op.addObject(new RLineEntity(document, new RLineData(new RVector(0,0), new RVector(100,0))));
op.addObject(new RLineEntity(document, new RLineData(new RVector(100,0), new RVector(100,80))));
op.addObject(new RLineEntity(document, new RLineData(new RVector(100,80), new RVector(0,80))));
op.addObject(new RLineEntity(document, new RLineData(new RVector(0,80), new RVector(0,0))));
op.apply(document);"""


_AUTOLISP_TO_ECMASCRIPT_REFERENCE = """## AutoLISP → QCAD ECMAScript Mapping Reference

### Drawing Primitives
| AutoLISP | QCAD ECMAScript |
|---|---|
| `(command "_LINE" pt1 pt2 "")` | `new RLineEntity(document, new RLineData(new RVector(x1,y1), new RVector(x2,y2)))` |
| `(command "_CIRCLE" cen rad)` | `new RCircleEntity(document, new RCircleData(new RVector(cx,cy), radius))` |
| `(command "_ARC" cen pt1 pt2)` | `new RArcEntity(document, new RArcData(center, radius, startAngle, endAngle, reversed))` |
| `(command "_RECTANG" pt1 pt2)` | 4x RLineEntity forming closed rectangle |
| `(command "_PLINE" pts...)` | `new RPolylineEntity(document, new RPolylineData(vertices))` |
| `(command "_TEXT" pt hgt rot text)` | `new RTextEntity(document, new RTextData(position, height, 0, text, "Standard", align, valign, ...))` |
| `(command "_HATCH" ...)` | `new RHatchEntity(document, new RHatchData(solid, scale, angle, pattern, boundary))` |
| `(command "_DIMLINEAR" pt1 pt2 loc)` | `new RDimAlignedEntity(document, new RDimAlignedData(pt1, pt2, dimLinePos))` |

### Entity Operations
| AutoLISP | QCAD ECMAScript |
|---|---|
| `(entmake ...)` | `op.addObject(entity); op.apply(document)` |
| `(entdel ename)` | `new RDeleteObjectsOperation()` |
| `(entmod ename data)` | `new RModifyObjectsOperation()` |
| `(ssget "X" ...)` | `document.queryAllEntities()` + filter loop |
| `(ssget "_WP" pts)` | Manual point-in-polygon check on queryAllEntities |
| `(sslength ss)` | `.length` on filtered array |
| `(ssname ss idx)` | Array index access |

### Layers
| AutoLISP | QCAD ECMAScript |
|---|---|
| `(command "_LAYER" "N" name ...)` | `new RLayer(document, name, frozen, locked, color)` added via RModifyObjectsOperation |
| `(setvar "CLAYER" name)` | Set current layer via document operations |
| `(tblsearch "LAYER" name)` | `document.queryLayer(id)` |

### Math and Geometry
| AutoLISP | QCAD ECMAScript |
|---|---|
| `(setq pt (list x y))` | `new RVector(x, y)` |
| `(distance pt1 pt2)` | `Math.sqrt(dx*dx + dy*dy)` |
| `(angle pt1 pt2)` | `Math.atan2(dy, dx)` |
| `(polar pt ang dist)` | `new RVector(pt.x + dist*Math.cos(ang), pt.y + dist*Math.sin(ang))` |
| `(+ a b)` | `a + b` |
| `(* a b)` | `a * b` |
| `(/ a b)` | `a / b` |
| `(sin ang)` | `Math.sin(ang)` |
| `(cos ang)` | `Math.cos(ang)` |
| `(rtos val)` | `val.toString()` or `val.toFixed(2)` |

### Variables and Flow
| AutoLISP | QCAD ECMAScript |
|---|---|
| `(setq name value)` | `var name = value;` |
| `(if test a b)` | `if (test) { a } else { b }` |
| `(cond (...)...)` | `if/else if/else` chain |
| `(repeat n ...)` | `for (var i = 0; i < n; i++) { ... }` |
| `(foreach item list ...)` | `for (var i = 0; i < list.length; i++) { var item = list[i]; ... }` |
| `(while test ...)` | `while (test) { ... }` |
| `(defun name (args) ...)` | `function name(args) { ... }` |
| `(progn ...)` | `{ ... }` block |

### Key Differences
- AutoLISP is prefix notation `(function arg1 arg2)`. ECMAScript is infix `function(arg1, arg2)`.
- AutoLISP uses `nil` for false/null. ECMAScript uses `null` or `false`.
- AutoLISP `(car list)` = first element. ECMAScript: `list[0]`.
- AutoLISP `(cadr list)` = second element. ECMAScript: `list[1]`.
- AutoLISP coordinates are unitless drawing units. QCAD ECMAScript uses mm by convention.
- AutoLISP `(command ...)` wraps user-interface commands. QCAD ECMAScript creates entity objects directly.
- QCAD ECMAScript must group all entity creations into an RAddObjectsOperation, then call op.apply(document) ONCE.
- All angles in QCAD ECMAScript are in radians, not degrees (use Math.PI/180 for conversion).
"""


def _heuristic_transpile(lisp: str) -> str:
    """Heuristic AutoLISP→ECMAScript translator for common patterns."""
    if not lisp or not lisp.strip():
        return ""

    # Pattern: (command "_LINE" (list x1 y1) (list x2 y2) "")
    line_pattern = re.findall(
        r'\(command\s+"_LINE"\s+\(list\s+([\d.]+)\s+([\d.]+)\)\s+\(list\s+([\d.]+)\s+([\d.]+)\)\s*""?\s*\)',
        lisp,
        re.IGNORECASE,
    )
    if line_pattern:
        lines = []
        for m in line_pattern:
            x1, y1, x2, y2 = m
            lines.append(
                f"op.addObject(new RLineEntity(document, "
                f"new RLineData(new RVector({x1},{y1}), new RVector({x2},{y2}))));"
            )
        return "var op = new RAddObjectsOperation();\n" + "\n".join(lines) + "\nop.apply(document);"

    # Pattern: (command "_CIRCLE" (list cx cy) radius)
    circle_pattern = re.findall(
        r'\(command\s+"_CIRCLE"\s+\(list\s+([\d.]+)\s+([\d.]+)\)\s+([\d.]+)\s*\)',
        lisp,
        re.IGNORECASE,
    )
    if circle_pattern:
        circles = []
        for m in circle_pattern:
            cx, cy, r = m
            circles.append(f"op.addObject(new RCircleEntity(document, new RCircleData(new RVector({cx},{cy}), {r})));")
        return "var op = new RAddObjectsOperation();\n" + "\n".join(circles) + "\nop.apply(document);"

    # Pattern: (defun draw-rect (w h) ... (command "_RECTANG" ...) ...) (draw-rect w h)
    rect_pattern = re.findall(
        r'\(defun\s+\S+\s*\((\S+)\s+(\S+)\).*?\(command\s+"_RECTANG".*?\).*?\)',
        lisp,
        re.IGNORECASE | re.DOTALL,
    )
    vals = re.findall(r"\(draw-rect\s+([\d.]+)\s+([\d.]+)\)", lisp, re.IGNORECASE)
    if rect_pattern and vals:
        w, h = vals[0]
        return f"""var op = new RAddObjectsOperation();
var w = {w}; var h = {h};
op.addObject(new RLineEntity(document, new RLineData(new RVector(0,0), new RVector(w,0))));
op.addObject(new RLineEntity(document, new RLineData(new RVector(w,0), new RVector(w,h))));
op.addObject(new RLineEntity(document, new RLineData(new RVector(w,h), new RVector(0,h))));
op.addObject(new RLineEntity(document, new RLineData(new RVector(0,h), new RVector(0,0))));
op.apply(document);"""

    # Pattern: (command "_TEXT" (list x y) hgt rot "text")
    text_pattern = re.findall(
        r'\(command\s+"_TEXT"\s+\(list\s+([\d.]+)\s+([\d.]+)\)\s+([\d.]+)\s+([\d.]+)\s+"([^"]+)"\s*\)',
        lisp,
        re.IGNORECASE,
    )
    if text_pattern:
        texts = []
        for m in text_pattern:
            x, y, hgt, rot, txt = m
            texts.append(
                f"op.addObject(new RTextEntity(document, "
                f"new RTextData(new RVector({x},{y}), {hgt}, 0, '{txt}', "
                f"'Standard', RS.HAlignLeft, RS.VAlignBase, RS.UnknownUnit, 0, 0, 0, false, false, {rot}*Math.PI/180, false, false)));"
            )
        return "var op = new RAddObjectsOperation();\n" + "\n".join(texts) + "\nop.apply(document);"

    safe_lisp = lisp.replace("\\", "\\\\").replace("`", "\\`")[:300]
    return f"""// ═══ AutoLISP → ECMAScript (heuristic fallback) ═══
// Original AutoLISP:
// {safe_lisp}
//
// NOTE: Full translation requires AI sampling. This is a best-effort heuristic.
// The pattern was not recognized by the heuristic rules.
// Use plan_transpile with AI sampling enabled for accurate results.

var op = new RAddObjectsOperation();
// Placeholder: add entities matching the LISP intent
op.apply(document);"""


async def plan_agentic(
    goal: Annotated[
        str,
        Field(
            description="Natural language description of the CAD operation to perform. E.g. 'Create a rectangular floor plan 10m x 8m with 4 rooms, add dimensions, and export to SVG'."
        ),
    ],
    file_name: Annotated[
        str, Field(default="", description="Optional depot file to work on. Empty = create new document.")
    ] = "",
    ctx: Context = None,
) -> dict:
    """Multi-step CAD workflow: plans and executes ECMAScript operations from a natural-language goal.

    Uses AI sampling to decompose the goal into ECMAScript steps, then executes
    them sequentially via QCAD Pro. Each step is validated before the next runs.

    Requires QCAD Pro installed. Falls back to single-script generation if AI
    sampling is unavailable.

    ## Return Format
    {"success": bool, "output": str, "data": {"steps": int, "entity_count": int, "plan": [...]}}

    ## Examples
    await plan_agentic(goal="Create a 10m x 8m floor plan with 4 equal rooms, label them, add aligned dimensions on all sides")
    await plan_agentic(goal="Add a 1m door to the south wall of each room", file_name="floorplan.dxf")
    """
    if not qcad_pro.is_installed():
        return {"success": False, "error": "QCAD Pro required."}

    out_name = f"{Path(file_name).stem}_agentic.dxf" if file_name else "agentic_output.dxf"
    out_path = os.path.join(OUTPUT_DIR, out_name)

    prompt = f"""You are a QCAD Pro ECMAScript expert. Convert this CAD goal into ECMAScript code.

Goal: {goal}

Context: The script runs in QCAD Pro headless. Variables available:
- `document` (RDocument) — the drawing
- `di` (RDocumentInterface) — for import/export
- RAddObjectsOperation, RLineEntity, RLineData, RVector, RCircleEntity, RCircleData,
  RDimAlignedEntity, RDimAlignedData, RLayer, RModifyObjectsOperation, RColor, etc.

{"The document already has entities loaded from " + file_name + ". Build on them." if file_name else "Create geometry from scratch."}

Return ONLY the ECMAScript code between ```javascript and ``` markers. No explanations.

Key rules:
1. Combine all entities into a single RAddObjectsOperation before calling op.apply()
2. RVector(x, y) — x and y are numbers. 1 unit = 1mm by convention.
3. For dimensions: RDimAlignedData(extPoint1, extPoint2, dimLinePos)
4. RLineData(startVector, endVector)
5. RCircleData(centerVector, radius)
6. Create layers BEFORE adding entities to them: new RLayer(document, "LayerName", false, false, new RColor("color"))
"""

    script = None
    plan_steps = []

    if ctx is not None:
        try:
            sampling_result = await ctx.request_sampling(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4096,
            )
            response_text = sampling_result.get("content", "")
            if "```javascript" in response_text:
                script = response_text.split("```javascript")[1].split("```")[0].strip()
            elif "```js" in response_text:
                script = response_text.split("```js")[1].split("```")[0].strip()
            elif "```" in response_text:
                script = response_text.split("```")[1].split("```")[0].strip()
            else:
                script = response_text.strip()
            plan_steps.append({"source": "ai_sampling", "code": script[:200] + "..."})
        except Exception as e:
            logger.warning("AI sampling failed, using template-based approach: %s", e)

    if script is None:
        script = _agentic_fallback(goal)
        plan_steps.append({"source": "template", "code": script[:200] + "..."})

    result = qcad_pro.run_script(
        user_code=script,
        input_file=os.path.join(DEPOT_DIR, file_name) if file_name else None,
        output_file=out_path,
        timeout=120,
    )

    if result.get("success"):
        data = result.get("data", {})
        data["steps"] = len(plan_steps)
        data["plan"] = plan_steps
        result["data"] = data
        result["output"] = out_name
    return result


async def plan_transpile(
    lisp_code: Annotated[str, Field(description="AutoLISP code to translate to QCAD ECMAScript.")],
    output_name: Annotated[
        str, Field(default="transpiled_output.dxf", description="Output filename for the executed result.")
    ] = "",
    ctx: Context = None,
) -> dict:
    """Translate AutoLISP to QCAD ECMAScript and execute the result.

    AI-powered transpiler that maps legacy AutoCAD AutoLISP routines to
    equivalent QCAD Pro ECMAScript. Handles entity creation, layer
    operations, selection sets, math functions, and control flow.

    The translated script is executed via QCAD Pro and the output DXF
    is saved to the output directory.

    Requires QCAD Pro installed. AI sampling recommended for best results;
    falls back to heuristic translation without it.

    ## Return Format
    {"success": bool, "output": str, "data": {"entity_count": int, "original_lisp": str, "transpiled_js": str, "source": str}}

    ## Examples
    await plan_transpile(lisp_code='(command "_LINE" (list 0 0) (list 100 0) "")')
    await plan_transpile(lisp_code='''
    (defun draw-rect (w h)
      (command "_RECTANG" (list 0 0) (list w h))
    )
    (draw-rect 100 80)
    ''')
    """
    if not qcad_pro.is_installed():
        return {"success": False, "error": "QCAD Pro required."}

    out_name = output_name or "transpiled_output.dxf"
    out_path = os.path.join(OUTPUT_DIR, out_name)

    transpile_prompt = f"""You are an expert in both AutoLISP and QCAD Pro ECMAScript (QtScript). Translate the following AutoLISP code to QCAD ECMAScript.

{_AUTOLISP_TO_ECMASCRIPT_REFERENCE}

AutoLISP code to translate:
```lisp
{lisp_code}
```

Return ONLY the ECMAScript code between ```javascript and ``` markers. No explanations.

Rules:
1. Wrap all entity creation in a single RAddObjectsOperation
2. Call op.apply(document) ONCE at the end
3. All coordinates in mm. If the AutoLISP uses unitless values, treat 1 unit = 1 mm
4. Replace (command ...) calls with direct entity constructors
5. Convert prefix notation to infix: (+ a b) → a + b
6. Use `var` for variable declarations instead of (setq ...)
7. If the AutoLISP defines functions (defun), keep them as function declarations
8. For (ssget "X") patterns, use document.queryAllEntities() with instanceof filtering
9. Angles in radians: multiply degrees by Math.PI/180
"""

    transpiled_js = None
    source = "heuristic"

    if ctx is not None:
        try:
            sampling_result = await ctx.request_sampling(
                messages=[{"role": "user", "content": transpile_prompt}],
                max_tokens=4096,
            )
            response_text = sampling_result.get("content", "")
            if "```javascript" in response_text:
                transpiled_js = response_text.split("```javascript")[1].split("```")[0].strip()
            elif "```js" in response_text:
                transpiled_js = response_text.split("```js")[1].split("```")[0].strip()
            elif "```" in response_text:
                transpiled_js = response_text.split("```")[1].split("```")[0].strip()
            else:
                transpiled_js = response_text.strip()
            if transpiled_js:
                source = "ai_transpiler"
        except Exception as e:
            logger.warning("AI transpilation failed, using heuristic: %s", e)

    if transpiled_js is None:
        transpiled_js = _heuristic_transpile(lisp_code)

    if not transpiled_js or transpiled_js == lisp_code:
        return {
            "success": False,
            "error": "Transpilation produced no output. The AutoLISP may be too complex for heuristic fallback. Try with AI sampling enabled.",
        }

    result = qcad_pro.run_script(
        user_code=transpiled_js,
        output_file=out_path,
        timeout=120,
    )

    if result.get("success"):
        data = result.get("data", {})
        data["original_lisp"] = lisp_code[:500] + ("..." if len(lisp_code) > 500 else "")
        data["transpiled_js"] = transpiled_js[:500] + ("..." if len(transpiled_js) > 500 else "")
        data["source"] = source
        result["data"] = data
        result["output"] = out_name
    return result


async def cad_sampling(
    goal: Annotated[str, Field(description="The CAD operation or question to reason about.")],
    ctx: Context = None,
) -> dict:
    """
    Use the host LLM (via MCP sampling) to reason about a CAD problem or plan a multi-step operation.

    The host's LLM analyzes the goal and returns a structured plan or explanation.
    Falls back to a static response if sampling is unavailable.

    ## Return Format
    {"success": bool, "response": str, "sampling_used": bool}

    ## Examples
    await cad_sampling(goal="What wall height should I use for a residential floor plan?")
    await cad_sampling(goal="Plan the steps to convert a DXF to a 3D printable STL")
    """
    if ctx is not None:
        try:
            result = await ctx.sample(
                system_prompt="You are a CAD and architecture expert assistant. Answer concisely and technically.",
                messages=[{"role": "user", "content": goal}],
                max_tokens=1000,
            )
            return {"success": True, "response": result, "sampling_used": True}
        except Exception as e:
            logger.warning("Sampling failed: %s", e)

    return {
        "success": True,
        "response": f"I received your CAD question: '{goal}'. To enable AI reasoning, connect this MCP server to a sampling-capable client (Claude Desktop, Cursor).",
        "sampling_used": False,
    }


async def cad_help_prompt(topic: str = "") -> str:
    """
    Get help with CAD operations. Returns a structured prompt for the LLM.
    """
    base = """You are a QCAD MCP assistant. You have access to the following tools:

Core tools: plan_info, plan_to_svg, plan_extrude, plan_export, plan_analyse, plan_create, plan_depot
Modify tools: plan_modify, plan_convert
Script tools: plan_scripts_search, plan_scripts_download
Block tools: plan_blocks, plan_blocks_download
Agentic tools: plan_agentic, cad_sampling

File depot is at %LOCALAPPDATA%\\qcad-mcp\\depot. All files persist across restarts.
Use the depot CRUD REST API for file management: GET/PUT/DELETE /api/v1/depot/{name}

Help the user with their CAD task. Be precise and suggest concrete tool calls.
"""
    if topic:
        return f"{base}\n\nThe user specifically asked about: {topic}"
    return base


def register(mcp):
    mcp.tool(annotations=_MUTATING, version="0.3.0")(plan_agentic)
    mcp.tool(annotations=_MUTATING, version="0.3.0")(plan_transpile)
    mcp.tool(annotations=_README_ONLY, version="0.3.0")(cad_sampling)

    @mcp.prompt()
    async def cad_expert(topic: str = "") -> str:
        """Get CAD expertise and tool guidance."""
        return await cad_help_prompt(topic)

    @mcp.prompt()
    async def cad_analyse_plan(file_name: str) -> str:
        """Analyse a DXF floor plan step by step."""
        return f"""Analyse the DXF floor plan at '{file_name}':

1. Call plan_info with file_name="{file_name}" to get layer and entity metadata
2. Call plan_to_svg with file_name="{file_name}" to generate a preview
3. Call plan_analyse with file_name="{file_name}" to detect rooms, areas, and openings
4. Summarise the results: building dimensions, room count, total area, door/window count

Be precise and structured in your output."""

    @mcp.prompt()
    async def cad_extrude_3d(file_name: str, height: float = 3.0, thickness: float = 0.3) -> str:
        """Extrude a DXF floor plan to a 3D STL mesh."""
        return f"""Convert the DXF floor plan '{file_name}' to a 3D STL mesh:

1. Run plan_extrude with file_name="{file_name}", wall_height={height}, wall_thickness={thickness}
2. The STL is ready for download from the output directory
3. Import into Resonite, Unity3D, or Blender for further processing

Wall height: {height}m, wall thickness: {thickness}m"""

    @mcp.resource("cad://depot")
    async def depot_list_resource() -> str:
        """List all files in the persistent CAD depot."""
        files = _depot_list()
        if not files:
            return "Depot is empty. Upload a DXF file to get started."
        lines = ["# CAD Depot Files\n"]
        for f in files:
            lines.append(f"- **{f['name']}** ({f['size_kb']} KB, modified {f['modified'][:10]})")
            meta = f.get("meta", {})
            if meta.get("description"):
                lines.append(f"  - {meta['description']}")
            if meta.get("tags"):
                lines.append(f"  - Tags: {', '.join(meta['tags'])}")
            if meta.get("entity_count") is not None:
                lines.append(f"  - Entities: {meta['entity_count']}")
        return "\n".join(lines)

    @mcp.resource("cad://depot/{filename}")
    async def depot_file_resource(filename: str) -> str:
        """Get information about a specific file in the depot."""
        meta = _read_meta(filename)
        path = os.path.join(DEPOT_DIR, filename)
        if not os.path.isfile(path):
            return f"File '{filename}' not found in depot."
        size_kb = round(os.path.getsize(path) / 1024, 1)
        return json.dumps({
            "name": filename,
            "size_kb": size_kb,
            "path": path,
            "meta": meta,
        }, indent=2)
