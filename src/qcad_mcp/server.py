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
import time
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import uvicorn
from fastapi import APIRouter, FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastmcp import FastMCP
from fastmcp.server import create_proxy
from pydantic import BaseModel, Field

from qcad_mcp.config import DEPOT_DIR, EXT_DXF, OUTPUT_DIR
from qcad_mcp.helpers import (
    _BLOCK_CATEGORIES,
    _depot_list,
    _doc_to_info,
    _ensure_meta,
    _get_ezdxf_version,
    _load_dxf,
    _meta_path,
    _read_meta,
    _write_meta,
)
from qcad_mcp.services import qcad_pro
from qcad_mcp.services.apps_routes import register_apps_routes
from qcad_mcp.tools import register_all
from qcad_mcp.tools.agentic_tools import plan_generate
from qcad_mcp.tools.annotation_tools import (
    plan_array,
    plan_beam_analysis,
    plan_block_insert,
    plan_dimension,
    plan_hatch,
    plan_measure,
    plan_text,
    plan_wall_data,
)
from qcad_mcp.tools.bim_tools import (
    plan_auto_dimension,
    plan_building_meta,
    plan_to_ifc_data,
)
from qcad_mcp.tools.block_tools import plan_blocks, plan_blocks_download
from qcad_mcp.tools.core_tools import (
    plan_analyse,
    plan_create,
    plan_depot,
    plan_drawings,
    plan_export,
    plan_extrude,
    plan_glb,
    plan_info,
    plan_obj,
    plan_stack,
    plan_to_svg,
)
from qcad_mcp.tools.modify_tools import plan_convert, plan_modify
from qcad_mcp.tools.qcad_tools import plan_exec, plan_render, plan_script, qcad_status
from qcad_mcp.tools.script_tools import _SCRIPT_CATEGORIES, plan_scripts_download, plan_scripts_search

logger = logging.getLogger("qcad-mcp")

_START_TIME = time.time()

# ── Lifespan ─────────────────────────────────────────────────────────────────

_state: dict = {}


def _tool_count() -> int:
    """Count registered FastMCP tools robustly across versions."""
    # FastMCP 3.4.x: no sync _tool_manager; list_tools() is async.
    # Sync fallback: REST dispatch table (populated at import) is a stable proxy.
    dispatch = globals().get("_TOOL_DISPATCH")
    if isinstance(dispatch, dict) and len(dispatch) > 0:
        return len(dispatch)
    for attr in ("_tools", "_registered_tools"):
        tools = getattr(mcp, attr, None)
        if isinstance(tools, dict) and len(tools) > 0:
            return len(tools)
    tm = getattr(mcp, "_tool_manager", None)
    if tm is not None and isinstance(getattr(tm, "tools", None), dict) and len(tm.tools) > 0:
        return len(tm.tools)
    return 0


async def _tool_count_async() -> int:
    """Async tool count via FastMCP 3.4 list_tools(), with sync fallback."""
    try:
        tools = await mcp.list_tools()
        return len(tools)
    except Exception:
        return _tool_count()


def _ensure_qcad_running():
    if not qcad_pro.is_installed():
        logger.info("QCAD Pro not installed - skipping auto-start")
        return False
    if qcad_pro.is_running():
        logger.info("QCAD Pro already running")
        return True
    # Tauri sidecar: skip GUI launch — runs headless in a non-interactive session
    # where spawning a GUI child hangs the piped-stdout backend.
    if os.environ.get("QCAD_TAURI") == "1" or os.environ.get("QCAD_MCP_TAURI") == "1":
        logger.info("QCAD_TAURI=1 - skipping QCAD Pro GUI auto-launch (headless sidecar)")
        return False
    qcad_exe = str(qcad_pro._qcad_base_dir() / "qcad.exe")
    if os.path.isfile(qcad_exe):
        try:
            CREATE_NEW_CONSOLE = 0x00000010
            subprocess.Popen(
                [qcad_exe],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=CREATE_NEW_CONSOLE,
            )
            logger.info("QCAD Pro GUI launched: %s", qcad_exe)
            return True
        except Exception as e:
            logger.warning("Failed to start QCAD Pro GUI: %s", e)
    return False


_QUIET_ACCESS_PATHS = ("/api/v1/status", "/api/v1/health", "/api/docs", "/openapi.json")


class _QuietProbesFilter(logging.Filter):
    """Drop uvicorn access-log lines for high-frequency health probes."""

    def filter(self, record):
        try:
            return not any(p in record.getMessage() for p in _QUIET_ACCESS_PATHS)
        except Exception:
            return True


def _quiet_probe_logs():
    try:
        logging.getLogger("uvicorn.access").addFilter(_QuietProbesFilter())
    except Exception:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    _quiet_probe_logs()
    _state["qcad_pro_ok"] = qcad_pro.is_installed()
    _state["qcad_pro_path"] = str(qcad_pro._qcad_base_dir())
    _ensure_qcad_running()
    _state["qcad_pro_running"] = qcad_pro.is_running()
    _state["qcad_pro_version"] = qcad_pro.get_version()
    _state["depot_dir"] = DEPOT_DIR
    _state["output_dir"] = OUTPUT_DIR
    _state["ezdxf_version"] = _get_ezdxf_version()
    logger.info(
        "QCAD MCP startup - ezdxf %s, QCAD Pro %s (%s), depot: %s",
        _state["ezdxf_version"],
        _state["qcad_pro_version"] or "not installed",
        "running" if _state.get("qcad_pro_running") else "not running",
        DEPOT_DIR,
    )
    yield


# ── FastAPI App ──────────────────────────────────────────────────────────────

app = FastAPI(lifespan=lifespan)

_QCAD_TAURI = os.environ.get("QCAD_TAURI", "").lower() in ("1", "true", "yes")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:11967",
        "http://localhost:11967",
        "http://goliath:11967",
        "http://tauri.localhost",
        "https://tauri.localhost",
        "tauri://localhost",
    ],
    allow_origin_regex=r"https?://tauri\.localhost(:\d+)?" if _QCAD_TAURI else None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

mcp = FastMCP.from_fastapi(app, name="QCAD MCP")

_bridge_proxies = []
bridge_urls = os.getenv("MCP_BRIDGE_URLS", "")
for url in bridge_urls.split(","):
    url = url.strip()
    if url:
        try:
            mcp.add_provider(create_proxy(url))
            _bridge_proxies.append(url)
        except Exception:
            logger.warning("Failed to register MCP bridge proxy for %s", url)

# ── MCP Tools ────────────────────────────────────────────────────────────────

register_all(mcp)


# ── REST API ──────────────────────────────────────────────────────────────────


# Apps hub routes mount under /api (the page calls /api/apps*).
_apps_router = APIRouter(prefix="/api")
register_apps_routes(_apps_router)
app.include_router(_apps_router)


@app.get("/api/v1/status")
async def api_status():
    """Server status including QCAD Pro and ezdxf info."""
    return {
        "ok": True,
        "ezdxf_version": _state.get("ezdxf_version", "unknown"),
        "qcad_pro": {
            "installed": qcad_pro.is_installed(),
            "running": qcad_pro.is_running(),
            "version": qcad_pro.get_version(),
            "install_dir": str(qcad_pro._qcad_base_dir()),
        },
        "depot": _state.get("depot_dir", ""),
        "output": _state.get("output_dir", ""),
        "file_count": len(_depot_list()),
    }


@app.get("/api/v1/health")
async def api_health():
    """Health endpoint with component status."""
    qcad_ok = qcad_pro.is_installed()
    qcad_version = qcad_pro.get_version()
    docker_ok = False
    try:
        r = await asyncio.to_thread(
            subprocess.run,
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        docker_ok = r.returncode == 0 and bool(r.stdout.strip())
    except Exception:
        docker_ok = False
    fluidx3d_path = os.environ.get("FLUIDX3D_PATH") or ""
    if not fluidx3d_path or not os.path.isdir(fluidx3d_path):
        candidate = r"D:\Dev\repos\FluidX3D"
        fluidx3d_path = candidate if os.path.isdir(candidate) else None
    compiler = None
    for exe in ["g++", "clang++", "cl.exe"]:
        try:
            cr = await asyncio.to_thread(subprocess.run, [exe, "--version"], capture_output=True, text=True, timeout=3)
            if cr.returncode == 0:
                compiler = exe
                break
        except Exception:
            logger.debug("Compiler probe failed for: %s", exe)
            continue
    tool_count = await _tool_count_async()
    return {
        "status": "ok" if qcad_ok else "degraded",
        "qcad_ok": qcad_ok,
        "qcad_version": qcad_version,
        "ezdxf_version": _state.get("ezdxf_version", "unknown"),
        "docker_available": docker_ok,
        "openfoam_image": docker_ok,
        "fluidx3d_path": fluidx3d_path,
        "compiler": compiler,
        "tool_count": tool_count,
        "uptime_seconds": time.time() - _START_TIME,
    }


@app.get("/api/v1/diagnostics")
async def api_diagnostics():
    try:
        import psutil

        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory().percent
        disk = psutil.disk_usage("/").percent
    except ImportError:
        cpu = mem = disk = None
    tool_count = await _tool_count_async()
    return {
        "success": True,
        "backend": {"port": 11966, "status": "running", "uptime": int(time.time() - _START_TIME)},
        "system": {"cpu_percent": cpu, "memory_percent": mem, "disk_percent": disk},
        "tools": {"total": tool_count},
        "cua_status": {"tesseract_available": False, "window_found": False},
    }


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


@app.get("/api/v1/scripts/categories")
async def scripts_categories():
    """List ECMAScript script categories."""
    return {"categories": [{"id": c, "label": c.capitalize()} for c in _SCRIPT_CATEGORIES]}


@app.get("/api/v1/scripts/search")
async def scripts_search(query: str = "", category: str = "", source: str = "all", limit: int = 20):
    """Search ECMAScript libraries via REST."""
    result = await plan_scripts_search(query=query, category=category, source=source, limit=limit)
    return result


@app.post("/api/v1/scripts/download")
async def scripts_download(body: dict):
    """Download an ECMAScript to the depot via REST."""
    result = await plan_scripts_download(
        title=body.get("title", "script"),
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
            results.append(
                {"file": fn, "success": r.get("success", False), "data": r.get("data", {}), "error": r.get("error")}
            )
        except Exception as e:
            results.append({"file": fn, "success": False, "error": str(e)})

    return {
        "tool": tool_name,
        "total": len(files),
        "success_count": sum(1 for r in results if r["success"]),
        "results": results,
    }


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


# ── REST Endpoints - Depot CRUD ─────────────────────────────────────────────


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


class _QcadShowRequest(BaseModel):
    file_name: str = Field(description="Drawing filename in depot (or outputs).")


@app.post("/api/v1/qcad/show")
async def qcad_show(req: _QcadShowRequest):
    """Open a drawing in the running QCAD Pro workspace (new tab)."""
    if ".." in req.file_name or req.file_name.startswith(("/", "\\")):
        raise HTTPException(400, "Invalid filename.")
    for base in (DEPOT_DIR, OUTPUT_DIR):
        path = os.path.join(base, req.file_name)
        if os.path.isfile(path):
            result = await asyncio.to_thread(qcad_pro.show_in_gui, path)
            if not result.get("success"):
                raise HTTPException(500, result.get("error", "Could not open in QCAD Pro."))
            return {"success": True, "file": req.file_name, **result}
    raise HTTPException(404, f"File '{req.file_name}' not found in depot or outputs.")


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


# ── REST Endpoints - DXF Creation ────────────────────────────────────────────


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


# ── REST Endpoints - Upload/Download Legacy ─────────────────────────────────


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
@app.get("/api/v1/case-files/{filename}")
@app.get("/api/v1/outputs/{filename}")
async def download_file(filename: str):
    safe = Path(filename).name
    if not safe or safe in (".", ".."):
        raise HTTPException(400, "Invalid filename")
    path = os.path.join(OUTPUT_DIR, safe)
    if not os.path.isfile(path):
        # plan_create stores DXFs in the depot; fall back so the Demo
        # page DXF download links (which hit this endpoint) resolve.
        depot_path = os.path.join(DEPOT_DIR, safe)
        if os.path.isfile(depot_path):
            path = depot_path
    if not os.path.isfile(path):
        raise HTTPException(404, f"File {safe} not found in output directory.")
    ext = Path(filename).suffix.lower()
    media_types = {
        ".svg": "image/svg+xml",
        ".stl": "application/sla",
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".dxf": "application/dxf",
        ".json": "application/json",
    }
    return FileResponse(path, media_type=media_types.get(ext, "application/octet-stream"), filename=filename)


@app.get("/api/v1/files")
async def list_files():
    uploads = []
    for f in os.listdir(DEPOT_DIR):
        fp = os.path.join(DEPOT_DIR, f)
        if os.path.isfile(fp) and not f.endswith(".meta.json"):
            uploads.append({"name": f, "size_kb": round(os.path.getsize(fp) / 1024, 1)})
    outputs = [
        {"name": f, "size_kb": round(os.path.getsize(os.path.join(OUTPUT_DIR, f)) / 1024, 1)}
        for f in os.listdir(OUTPUT_DIR)
        if os.path.isfile(os.path.join(OUTPUT_DIR, f))
    ]
    return {"uploads": uploads, "outputs": outputs}


# ── REST Endpoints - Tool Bridge ──────────────────────────────────────────────


# Tool dispatch: maps tool name -> (function, param_extractor)
# param_extractor extracts kwargs from the raw args dict.
_TOOL_DISPATCH: dict[str, tuple] = {}


def _register_tool(name: str, fn, param_map: dict[str, str] | None = None):
    """Register a tool for REST dispatch. param_map: arg_key -> function_param_name."""
    _TOOL_DISPATCH[name] = (fn, param_map or {})


def _extract(args: dict, key: str, default=None):
    """Extract a value from args, trying both key and underscored variants."""
    return args.get(key, args.get(key.replace("-", "_"), default))


# ── Register all REST-accessible tools ─────────────────────────────────────

_register_tool("plan_info", plan_info, {"file_name": "file_name"})
_register_tool(
    "plan_to_svg",
    plan_to_svg,
    {"file_name": "file_name", "output_name": "output_name", "layers": "layers", "background": "background"},
)
_register_tool(
    "plan_extrude",
    plan_extrude,
    {
        "file_name": "file_name",
        "output_name": "output_name",
        "wall_height": "wall_height",
        "wall_thickness": "wall_thickness",
        "wall_layers": "wall_layers",
        "base_elevation": "base_elevation",
        "slab": "slab",
        "slab_thickness": "slab_thickness",
    },
)
_register_tool("plan_export", plan_export, {"file_name": "file_name", "format": "format", "output_name": "output_name"})
_register_tool(
    "plan_stack",
    plan_stack,
    {
        "files": "files",
        "output_name": "output_name",
        "wall_height": "wall_height",
        "wall_thickness": "wall_thickness",
        "wall_layers": "wall_layers",
        "slab": "slab",
        "slab_thickness": "slab_thickness",
    },
)
_register_tool(
    "plan_obj",
    plan_obj,
    {
        "file_name": "file_name",
        "output_name": "output_name",
        "wall_height": "wall_height",
        "wall_thickness": "wall_thickness",
        "wall_layers": "wall_layers",
        "base_elevation": "base_elevation",
        "textured": "textured",
        "slab": "slab",
        "slab_thickness": "slab_thickness",
        "green_roof": "green_roof",
    },
)
_register_tool(
    "plan_glb",
    plan_glb,
    {
        "file_name": "file_name",
        "obj_name": "obj_name",
        "output_name": "output_name",
        "wall_height": "wall_height",
        "wall_thickness": "wall_thickness",
        "wall_layers": "wall_layers",
        "green_roof": "green_roof",
    },
)
_register_tool(
    "plan_drawings",
    plan_drawings,
    {
        "file_name": "file_name",
        "output_prefix": "output_prefix",
        "wall_height": "wall_height",
        "wall_thickness": "wall_thickness",
        "wall_layers": "wall_layers",
        "views": "views",
        "background": "background",
    },
)
_register_tool("plan_analyse", plan_analyse, {"file_name": "file_name"})
_register_tool(
    "plan_create",
    plan_create,
    {"filename": "filename", "entities": "entities", "layers": "layers", "description": "description"},
)
_register_tool("plan_depot", plan_depot, {})
_register_tool("plan_convert", plan_convert, {"file_name": "file_name", "output_name": "output_name"})
_register_tool("plan_modify", plan_modify, {"file_name": "file_name", "operations": "operations"})
_register_tool(
    "plan_blocks", plan_blocks, {"query": "query", "category": "category", "source": "source", "limit": "limit"}
)
_register_tool("plan_blocks_download", plan_blocks_download, {"title": "title", "source": "source", "url": "url"})
_register_tool("qcad_status", qcad_status, {})
_register_tool(
    "plan_scripts_search",
    plan_scripts_search,
    {"query": "query", "category": "category", "source": "source", "limit": "limit"},
)
_register_tool("plan_scripts_download", plan_scripts_download, {"title": "title", "source": "source", "url": "url"})
_register_tool("plan_beam_analysis", plan_beam_analysis, {"beams": "beams", "supports": "supports", "loads": "loads"})
_register_tool("plan_measure", plan_measure, {"file_name": "file_name"})
_register_tool(
    "plan_wall_data",
    plan_wall_data,
    {"file_name": "file_name", "wall_layers": "wall_layers", "wall_thickness": "wall_thickness"},
)
_register_tool(
    "plan_dimension",
    plan_dimension,
    {"file_name": "file_name", "dimensions": "dimensions", "output_name": "output_name"},
)
_register_tool("plan_text", plan_text, {"file_name": "file_name", "texts": "texts", "output_name": "output_name"})
_register_tool("plan_hatch", plan_hatch, {"file_name": "file_name", "hatches": "hatches", "output_name": "output_name"})
_register_tool(
    "plan_block_insert",
    plan_block_insert,
    {"file_name": "file_name", "inserts": "inserts", "output_name": "output_name"},
)
_register_tool(
    "plan_array",
    plan_array,
    {
        "file_name": "file_name",
        "pattern": "pattern",
        "count": "count",
        "params": "params",
        "output_name": "output_name",
    },
)
_register_tool("plan_script", plan_script, {"code": "code", "file_name": "file_name", "output_name": "output_name"})
_register_tool("plan_render", plan_render, {"file_name": "file_name", "format": "format", "output_name": "output_name"})
_register_tool("plan_exec", plan_exec, {"code": "code", "file_name": "file_name"})
_register_tool(
    "plan_auto_dimension",
    plan_auto_dimension,
    {"file_name": "file_name", "wall_layers": "wall_layers", "offset": "offset", "output_name": "output_name"},
)
_register_tool(
    "plan_building_meta",
    plan_building_meta,
    {"file_name": "file_name", "level_name": "level_name", "elevation": "elevation"},
)
_register_tool(
    "plan_to_ifc_data",
    plan_to_ifc_data,
    {
        "file_name": "file_name",
        "wall_layers": "wall_layers",
        "wall_height": "wall_height",
        "wall_thickness": "wall_thickness",
    },
)


class ToolRequest(BaseModel):
    tool: str = Field(description=f"Tool name: {', '.join(sorted(_TOOL_DISPATCH.keys()))}")
    arguments: dict = Field(default_factory=dict, description="Tool arguments as a dict")


_register_tool(
    "plan_generate",
    plan_generate,
    {"goal": "goal", "filename": "filename", "model": "model", "create_dxf": "create_dxf"},
)


@app.post("/api/v1/control/tool")
async def execute_tool(req: ToolRequest):
    t = req.tool
    if t not in _TOOL_DISPATCH:
        raise HTTPException(400, f"Unknown tool: {t}. Available: {', '.join(sorted(_TOOL_DISPATCH.keys()))}")
    fn, param_map = _TOOL_DISPATCH[t]
    kwargs = {}
    for arg_key, param_name in param_map.items():
        val = _extract(req.arguments, arg_key)
        if val is not None:
            kwargs[param_name] = val
    return await fn(**kwargs)


# ── MCP-only tools (need Context) ──────────────────────────────────────────
# plan_agentic, plan_transpile, cad_sampling use sampling and are only
# available via MCP protocol, not REST. plan_generate is on REST too: without
# a sampling client it uses the local Ollama model instead.


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


# ── FloatingChat LLM Endpoints ────────────────────────────────────────────────
# Local Ollama first (fleet default); the old LAN default is unreachable here.

_LLM_DEFAULT_URL = "http://127.0.0.1:11434"
_LLM_NUM_CTX = 32768  # cap: long-ctx models default to 262k KV (CPU offload, ~3 tok/s)


@app.get("/api/llm/providers")
async def llm_providers():
    models: list[str] = []
    ollama_url = _llm_settings.get("ollama_url", _LLM_DEFAULT_URL)
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{ollama_url}/api/tags")
            for m in r.json().get("models", []):
                name = m.get("name", "")
                if name:
                    models.append(name)
    except Exception:
        pass
    return {"providers": [{"name": "ollama", "models": models}]}


class LlmChatRequest(BaseModel):
    provider: str = "ollama"
    model: str = ""
    prompt: str = ""
    system: str = ""


@app.post("/api/llm/chat")
async def llm_chat(req: LlmChatRequest):
    # Send-time guard (fleet SETTINGS_LLM rule 6): no fallback model, ever.
    model = req.model or _llm_settings.get("model", "")
    if not model:
        return {"error": "No model selected - pick one in Settings > LLM Provider."}
    ollama_url = _llm_settings.get("ollama_url", _LLM_DEFAULT_URL)
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"{ollama_url}/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": req.system or "You are a CAD and floor plan expert."},
                        {"role": "user", "content": req.prompt},
                    ],
                    "stream": False,
                    "options": {"num_ctx": _LLM_NUM_CTX},
                },
            )
            try:
                data = r.json()
            except Exception:
                data = {}
            if r.status_code != 200:
                detail = data.get("error", "") if isinstance(data, dict) else ""
                return {"error": f"Ollama error: {detail or (r.text or '')[:300]}"}
            content = (data.get("message") or {}).get("content", "") or data.get("response", "")
            if not content:
                return {"error": f"Ollama returned no content (model '{model}' installed?)."}
            return {"response": content}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/llm/models")
async def llm_models(provider: str = "ollama"):
    """Live model list for the chat/settings selectors (source: live)."""
    if provider != "ollama":
        return {"provider": provider, "models": [], "source": "none"}
    ollama_url = _llm_settings.get("ollama_url", _LLM_DEFAULT_URL)
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(f"{ollama_url}/api/tags")
            names = [m.get("name", "") for m in r.json().get("models", [])]
            return {"provider": provider, "models": [n for n in names if n], "source": "live"}
    except Exception:
        return {"provider": provider, "models": [], "source": "none"}


@app.get("/api/llm/loaded")
async def llm_loaded(provider: str = "ollama", endpoint: str = ""):
    """Models currently resident on the local engine (Settings KPI)."""
    from qcad_mcp.services.llm_engine import ollama_loaded

    if provider != "ollama":
        return {"success": False, "engine": False, "models": []}
    data = await ollama_loaded(endpoint or _llm_settings.get("ollama_url", _LLM_DEFAULT_URL))
    return {"success": True, **data}


@app.get("/api/llm/gpus")
async def llm_gpus():
    """Live per-GPU VRAM telemetry ([] without NVIDIA driver)."""
    from qcad_mcp.services.llm_engine import gpu_vram

    return {"gpus": gpu_vram()}


@app.post("/api/llm/unload")
async def llm_unload(body: dict | None = None):
    """Kick-out: evict every resident model (loads nothing)."""
    from qcad_mcp.services.llm_engine import switch_ollama_model

    endpoint = (body or {}).get("endpoint") or _llm_settings.get("ollama_url", _LLM_DEFAULT_URL)
    result = await switch_ollama_model("", endpoint)
    if not result.get("engine"):
        raise HTTPException(502, "Ollama engine unreachable.")
    return {"success": True, "evicted": result.get("evicted", [])}


# ── Chat / LLM ───────────────────────────────────────────────────────────────

_llm_settings = {"ollama_url": _LLM_DEFAULT_URL, "model": ""}


class ChatRequest(BaseModel):
    messages: list[dict] = []
    system: str = ""
    provider: str = "ollama"
    model: str = ""


class SettingsUpdate(BaseModel):
    ollama_url: str | None = None
    model: str | None = None
    qcad_pro_path: str | None = None
    default_wall_height: float | None = None
    default_wall_thickness: float | None = None


_app_settings = {"default_wall_height": 3.0, "default_wall_thickness": 0.3}

_SETTINGS_FILE = os.environ.get(
    "QCAD_SETTINGS_FILE",
    os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "qcad-mcp", "settings.json"),
)


def _load_persisted_settings():
    """Restore settings saved by PUT /api/v1/settings (memory alone loses the model on restart)."""
    try:
        with open(_SETTINGS_FILE) as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return
        for k in ("ollama_url", "model"):
            if data.get(k):
                _llm_settings[k] = data[k]
        for k in ("default_wall_height", "default_wall_thickness"):
            if isinstance(data.get(k), (int, float)):
                _app_settings[k] = data[k]
        if data.get("qcad_pro_path"):
            _state["qcad_pro_path"] = data["qcad_pro_path"]
    except Exception:
        pass


def _save_persisted_settings():
    try:
        os.makedirs(os.path.dirname(_SETTINGS_FILE), exist_ok=True)
        with open(_SETTINGS_FILE, "w") as f:
            json.dump(
                {
                    "ollama_url": _llm_settings.get("ollama_url"),
                    "model": _llm_settings.get("model", ""),
                    "default_wall_height": _app_settings.get("default_wall_height"),
                    "default_wall_thickness": _app_settings.get("default_wall_thickness"),
                    "qcad_pro_path": _state.get("qcad_pro_path", ""),
                },
                f,
                indent=2,
            )
    except Exception as e:
        logger.warning("Could not persist settings: %s", e)


_load_persisted_settings()


@app.get("/api/v1/settings")
async def get_settings():
    return {
        **_llm_settings,
        **_app_settings,
        "qcad_pro_path": _state.get("qcad_pro_path", ""),
        "qcad_pro_ok": _state.get("qcad_pro_ok", False),
    }


@app.put("/api/v1/settings")
async def update_settings(body: SettingsUpdate):
    from qcad_mcp.services.llm_engine import switch_ollama_model

    if body.ollama_url:
        _llm_settings["ollama_url"] = body.ollama_url
    llm_switch: dict | None = None
    if body.model is not None:
        # Save switches VRAM, not just config (fleet SETTINGS_LLM rule 4).
        _llm_settings["model"] = body.model
        if body.model:
            llm_switch = await switch_ollama_model(body.model, _llm_settings["ollama_url"])
    if body.qcad_pro_path:
        _state["qcad_pro_path"] = body.qcad_pro_path
        _state["qcad_pro_ok"] = os.path.isfile(body.qcad_pro_path)
    if body.default_wall_height is not None:
        _app_settings["default_wall_height"] = body.default_wall_height
    if body.default_wall_thickness is not None:
        _app_settings["default_wall_thickness"] = body.default_wall_thickness
    _save_persisted_settings()
    return {
        **_llm_settings,
        **_app_settings,
        "qcad_pro_path": _state.get("qcad_pro_path", ""),
        "qcad_pro_ok": _state.get("qcad_pro_ok", False),
        "llm_switch": llm_switch,
    }


@app.post("/api/v1/chat")
async def chat_completion(req: ChatRequest):
    url = req.provider == "ollama" and f"{_llm_settings.get('ollama_url', _LLM_DEFAULT_URL)}/api/chat"
    model = req.model or _llm_settings.get("model", "")
    if not model:
        return {"content": "No model selected - pick one in Settings > LLM Provider."}
    if not url:
        return {"content": "Only Ollama provider is supported currently."}
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(
                url,
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": req.system or "You are a CAD and floor plan expert."},
                        *req.messages,
                    ],
                    "stream": False,
                    "options": {"num_ctx": _LLM_NUM_CTX},
                },
            )
            data = r.json()
            return {"content": (data.get("message") or {}).get("content", "") or data.get("response", "")}
    except Exception as e:
        logger.error("Chat error: %s", e)
        return {"content": f"Error: {e}"}


# ── AI Floor-Plan Generation ──────────────────────────────────────────────
# The Demo webapp's free-text box posts here FIRST; the keyword templates in
# the webapp are the fallback, never the primary path. Local Ollama only,
# no model fallback (fleet SETTINGS_LLM rule 6): without a selected model
# this refuses with code "no-model" and the caller uses templates.


class AiGeneratePlanRequest(BaseModel):
    goal: str = Field(description="Natural-language floor plan description.")
    model: str = Field(default="", description="Ollama model override. Default: Settings model.")


@app.post("/api/v1/ai/generate-plan")
async def ai_generate_plan(req: AiGeneratePlanRequest):
    """Turn a natural-language goal into plan_create entity JSON via local LLM."""
    from qcad_mcp.services import plan_llm

    goal = (req.goal or "").strip()
    if not goal:
        return {"success": False, "code": "empty", "error": "Empty goal."}
    if len(goal) > 2000:
        return {"success": False, "code": "too-long", "error": "Goal over 2000 characters."}
    model = req.model or _llm_settings.get("model", "")
    if not model:
        return {
            "success": False,
            "code": "no-model",
            "error": "No LLM model selected - pick one in Settings > LLM Provider. Using template fallback.",
        }
    ollama_url = _llm_settings.get("ollama_url", _LLM_DEFAULT_URL)
    try:
        raw = await plan_llm.chat_generate(goal, model, ollama_url)
    except plan_llm.PlanLlmError as e:
        logger.warning("ai_generate_plan LLM call failed [%s]: %s", e.code, e)
        return {"success": False, "code": e.code, "error": str(e)}
    try:
        data = plan_llm.extract_plan_json(raw)
    except plan_llm.PlanLlmError as e:
        logger.warning("ai_generate_plan JSON extract failed: %s", e)
        return {"success": False, "code": e.code, "error": str(e), "model": model}
    try:
        spec, warnings = plan_llm.validate_plan(data)
    except plan_llm.PlanLlmError as e:
        logger.warning("ai_generate_plan validation failed: %s", e)
        return {"success": False, "code": e.code, "error": str(e), "model": model}
    return {"success": True, "source": "llm", "model": model, "warnings": warnings, **spec}


# ── Blender Handoff (fleet cross-connect) ─────────────────────────────────
# Sends qcad OBJ/STL output to blender-mcp via its MCP endpoint
# (POST /mcp JSON-RPC: initialize -> tools/call blender_import).
# global_scale 0.001 converts our millimetres to Blender metres.

_BLENDER_BASE = os.environ.get("BLENDER_MCP_URL", "http://127.0.0.1:10849")


def _parse_mcp_sse(text):
    """Extract the last data: payload from an MCP SSE/JSON response."""
    payload = None
    for line in (text or "").splitlines():
        if line.startswith("data: "):
            try:
                payload = json.loads(line[6:])
            except Exception:
                pass
    if payload is None:
        try:
            payload = json.loads(text)
        except Exception:
            payload = None
    return payload


async def _blender_rpc(method, params=None, rpc_id=1, session=None, notify=False, timeout=180.0):
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    if session:
        headers["Mcp-Session-Id"] = session
    body = {"jsonrpc": "2.0", "method": method}
    if not notify:
        body["id"] = rpc_id
    if params is not None:
        body["params"] = params
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(_BLENDER_BASE + "/mcp", json=body, headers=headers)
        return r.headers.get("Mcp-Session-Id", session), _parse_mcp_sse(r.text)


@app.get("/api/v1/blender/status")
async def blender_status():
    """Probe the blender-mcp backend for the render handoff."""
    for path in ("/api/v1/health", "/api/v1/status"):
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(_BLENDER_BASE + path)
                if r.status_code == 200:
                    return {"reachable": True, "base": _BLENDER_BASE, "status": r.json()}
        except Exception:
            continue
    return {
        "reachable": False,
        "base": _BLENDER_BASE,
        "hint": "Start the blender-mcp backend to enable textured render import.",
    }


class BlenderImportRequest(BaseModel):
    file_name: str = Field(description="OBJ/STL/GLB filename in qcad outputs, e.g. plan.obj")
    operation: str = Field(default="", description="MCP operation (default by extension).")
    global_scale: float = Field(default=0.001, description="Unit scale, mm to Blender metres.")


@app.post("/api/v1/blender/import")
async def blender_import(req: BlenderImportRequest):
    """Send a qcad 3D file to Blender (textured OBJ keeps materials)."""
    obj_path = os.path.join(OUTPUT_DIR, req.file_name)
    if not os.path.isfile(obj_path):
        raise HTTPException(404, f"File '{req.file_name}' not found in qcad outputs.")
    ext = Path(req.file_name).suffix.lower()
    op = req.operation or {"obj": "import_obj", "stl": "import_stl", "glb": "import_gltf", "gltf": "import_gltf"}.get(
        ext.lstrip("."), ""
    )
    if not op:
        raise HTTPException(400, f"Unsupported extension for Blender import: {ext}")
    try:
        session, _ = await _blender_rpc(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "qcad-shuttle", "version": "1"},
            },
            rpc_id=1,
            timeout=60.0,
        )
        if not session:
            raise RuntimeError("Blender MCP session failed.")
        await _blender_rpc("notifications/initialized", None, session=session, notify=True, timeout=30.0)
        _session, payload = await _blender_rpc(
            "tools/call",
            {
                "name": "blender_import",
                "arguments": {
                    "operation": op,
                    "filepath": obj_path,
                    "file_format": ext.lstrip(".").upper(),
                    "global_scale": req.global_scale,
                    "import_shading": True,
                },
            },
            rpc_id=3,
            session=session,
            timeout=300.0,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Blender backend unreachable at {_BLENDER_BASE}: {e}")
    detail = ""
    inner = {}
    try:
        content = (payload.get("result", {}) or {}).get("content", [])
        detail = (content[0] or {}).get("text", "") if content else ""
        inner = json.loads(detail) if detail else {}
    except Exception:
        pass
    if inner.get("status") != "SUCCESS":
        raise HTTPException(502, f"Blender import failed: {(inner.get('error') or detail)[:300]}")
    return {"success": True, "output": req.file_name, "data": inner, "detail": detail[:500]}


# ── Resonite Handoff (fleet cross-connect) ─────────────────────────────────
# Stages a GLB (Resonite imports .glb/.gltf/.vrm only) and spawns it in the
# running game client: link check via /rl/status?autoconnect=true (UDP 12512
# discovery, no hardcoded port), then /rl/world/spawn-model (GLB -> mesh
# JSON -> spawn_mesh over the live link). Generic ResoniteLink file import
# does not exist (protocol 0.13.1); the mesh-JSON spawn chain is the wired
# hop. The old OSC inventory-upload path is retired: nothing game-side
# consumes /inventory/upload (no UDP 9000 listener).

_RESONITE_BASE = os.environ.get("RESONITE_MCP_URL", "http://127.0.0.1:10979")


@app.get("/api/v1/resonite/status")
async def resonite_status():
    """Probe the resonite-mcp backend for the VR handoff."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(_RESONITE_BASE + "/api/v1/health")
            if r.status_code == 200:
                return {"reachable": True, "base": _RESONITE_BASE, "status": r.json()}
    except Exception:
        pass
    return {
        "reachable": False,
        "base": _RESONITE_BASE,
        "hint": "Start the resonite-mcp backend to enable VR delivery.",
    }


class ResoniteImportRequest(BaseModel):
    file_name: str = Field(description="DXF in depot or OBJ/GLB in outputs; GLB is produced as needed.")
    output_name: str = Field(default="", description="GLB filename. Default: <stem>.glb.")
    link_port: int = Field(
        default=0,
        description="ResoniteLink port of the target world (see GET /api/v1/resonite/sessions). "
        "0 = follow the most recently announced world.",
    )
    pos_x: float = Field(default=0.0, description="Spawn position in world (avoids piling at origin).")
    pos_y: float = Field(default=0.0, description="Spawn position in world.")
    pos_z: float = Field(default=0.0, description="Spawn position in world.")


@app.get("/api/v1/resonite/sessions")
async def resonite_sessions(timeout_seconds: float = 12.0):
    """List Resonite worlds announcing a link (UDP 12512) with their ports."""
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds + 15) as client:
            d = await client.get(_RESONITE_BASE + "/rl/discover", params={"timeout_seconds": timeout_seconds})
            if d.status_code != 200:
                raise HTTPException(502, f"Discovery failed: {(d.text or '')[:200]}")
            return d.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"resonite-mcp unreachable at {_RESONITE_BASE}: {e}")


@app.post("/api/v1/resonite/import")
async def resonite_import(req: ResoniteImportRequest):
    """Stage a GLB for Resonite and spawn it in the target world."""
    glb_name, glb_path = await _ensure_glb(req.file_name, req.output_name)
    glb_kb = round(os.path.getsize(glb_path) / 1024, 1) if os.path.isfile(glb_path) else 0.0

    def _staged(delivery: dict) -> dict:
        return {
            "success": True,
            "output": glb_name,
            "download": f"/api/v1/download/{glb_name}",
            "size_kb": glb_kb,
            "delivery": delivery,
        }

    link_info, world_name, link_error = await _resonite_link(req.link_port)
    if link_error is not None:
        return _staged(link_error)
    assert link_info is not None and world_name is not None
    delivery = await _spawn_glb(link_info, world_name, glb_path, Path(glb_name).stem, req.pos_x, req.pos_y, req.pos_z)
    return _staged(delivery)


class ResoniteTowerLevel(BaseModel):
    file_name: str = Field(description="DXF in depot or OBJ/GLB in outputs.")
    y: float = Field(default=0.0, description="World Y (meters) for this storey.")


class ResoniteImportTowerRequest(BaseModel):
    levels: list[ResoniteTowerLevel] = Field(description="Storeys bottom-up; each converted and spawned at its Y.")
    link_port: int = Field(default=0, description="Target world port (0 = most recently announced).")
    pos_x: float = Field(default=0.0, description="Shared world X for the stack.")
    pos_z: float = Field(default=0.0, description="Shared world Z for the stack.")


@app.post("/api/v1/resonite/import-tower")
async def resonite_import_tower(req: ResoniteImportTowerRequest):
    """Convert each storey DXF to GLB and spawn the stack at its elevations."""
    if not req.levels:
        raise HTTPException(400, "No levels given.")
    link_info, world_name, link_error = await _resonite_link(req.link_port)
    if link_error is not None:
        return {"success": True, "delivery": link_error, "spawned": []}
    assert link_info is not None and world_name is not None
    spawned: list[dict] = []
    try:
        for lv in req.levels:
            glb_name, glb_path = await _ensure_glb(lv.file_name)
            delivery = await _spawn_glb(
                link_info, world_name, glb_path, Path(glb_name).stem, req.pos_x, lv.y, req.pos_z
            )
            spawned.append({"file": lv.file_name, "glb": glb_name, "y": lv.y, **delivery})
    except HTTPException as e:
        spawned.append({"file": lv.file_name, "delivered": False, "reason": e.detail})
    ok = spawned and all(s.get("delivered") for s in spawned)
    return {
        "success": True,
        "delivery": {
            "delivered": bool(ok),
            "detail": f"Spawned {len([s for s in spawned if s.get('delivered')])}/{len(spawned)} storeys "
            f"in world '{world_name}' at ({req.pos_x}, +storey, {req.pos_z}).",
        },
        "spawned": spawned,
    }


async def _ensure_glb(file_name: str, output_name: str = "") -> tuple[str, str]:
    """Convert DXF/OBJ to GLB as needed. Returns (glb_name, glb_path). Raises HTTPException."""
    from qcad_mcp.tools.core_tools import plan_glb

    ext = Path(file_name).suffix.lower()
    if ext == ".dxf":
        conv = await plan_glb(file_name=file_name, output_name=output_name)
        if not conv.get("success"):
            raise HTTPException(500, conv.get("error", "GLB conversion failed."))
        glb_name = conv["output"]
    elif ext in (".obj", ".glb", ".gltf"):
        src = os.path.join(OUTPUT_DIR, file_name)
        if not os.path.isfile(src):
            raise HTTPException(404, f"File '{file_name}' not found in qcad outputs.")
        if ext == ".obj":
            conv = await plan_glb(obj_name=file_name, output_name=output_name)
            if not conv.get("success"):
                raise HTTPException(500, conv.get("error", "GLB conversion failed."))
            glb_name = conv["output"]
        else:
            glb_name = file_name
    else:
        raise HTTPException(400, f"Unsupported file for Resonite: {ext} (use DXF, OBJ, GLB).")
    return glb_name, os.path.join(OUTPUT_DIR, glb_name)


async def _resonite_link(link_port: int) -> tuple[dict | None, str | None, dict | None]:
    """Discover worlds and (re)connect to the target. Returns (link_info, world_name, error)."""
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            d = await client.get(_RESONITE_BASE + "/rl/discover", params={"timeout_seconds": 12})
            sessions = (d.json() if d.status_code == 200 else {}).get("sessions", [])
    except Exception as e:
        return (
            None,
            None,
            {
                "delivered": False,
                "reason": f"resonite-mcp unreachable at {_RESONITE_BASE}: {e}",
                "detail": "Start the resonite-mcp backend to enable VR delivery.",
            },
        )
    if not sessions:
        # UDP discovery (port 12512) is flaky: firewalled hosts and focused
        # sessions often announce nothing while the TCP link is healthy and
        # connected (seen 2026-09-20: /rl/status connected on localhost:30418
        # with zero discovered sessions). Fall back to the live link instead
        # of failing a spawn the game client would accept.
        try:
            async with httpx.AsyncClient(timeout=15) as _sc:
                _s = await _sc.get(_RESONITE_BASE + "/rl/status")
                _cur = _s.json() if _s.status_code == 200 else {}
            if _cur.get("connected"):
                _link = {
                    "connected": True,
                    "host": _cur.get("host"),
                    "port": _cur.get("port"),
                    "world": "connected world (discovery silent)",
                    "session_info": _cur.get("session_info"),
                    "discovery": "silent-fallback",
                }
                return _link, "connected world", None
        except Exception:
            pass
        return (
            None,
            None,
            {
                "delivered": False,
                "reason": "No Resonite session found via link discovery and no live link.",
                "detail": "Is Resonite running with ResoniteLink enabled in the active "
                "session? (Dashboard -> Session -> Settings.) "
                "GET /api/v1/resonite/sessions was empty and /rl/status is not connected.",
            },
        )
    target = None
    if link_port:
        target = next((s for s in sessions if int(s.get("linkPort", 0)) == link_port), None)
        if target is None:
            return (
                None,
                None,
                {
                    "delivered": False,
                    "reason": f"World on link port {link_port} is not announcing. "
                    f"Live worlds: {', '.join(s.get('sessionName', '?') for s in sessions)}.",
                    "detail": "Pick a port from GET /api/v1/resonite/sessions.",
                },
            )
    else:
        target = max(sessions, key=lambda s: s.get("lastSeen", 0))
    world_name = target.get("sessionName", "?")
    target_port = int(target.get("linkPort", 0))
    announced_host = target.get("host") or "localhost"
    if announced_host == "0.0.0.0":  # noqa: S104 -- string compare, not a bind
        announced_host = "localhost"
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            s = await client.get(_RESONITE_BASE + "/rl/status")
            cur = s.json() if s.status_code == 200 else {}
            if not cur.get("connected") or int(cur.get("port") or 0) != target_port:
                # A loopback-bound link server is announced with the sender's
                # LAN address but only answers on localhost: try both.
                hosts = [announced_host] + ([] if announced_host in ("localhost", "127.0.0.1") else ["localhost"])
                connected = False
                last_err = "no candidate host"
                for h in hosts:
                    c = await client.post(_RESONITE_BASE + "/rl/connect", json={"host": h, "port": target_port})
                    if c.status_code == 200:
                        connected = True
                        break
                    last_err = (c.text or "")[:200]
                if not connected:
                    return (
                        None,
                        None,
                        {
                            "delivered": False,
                            "reason": f"Found world '{world_name}' but could not connect to its link.",
                            "detail": last_err,
                        },
                    )
                s = await client.get(_RESONITE_BASE + "/rl/status")
                cur = s.json() if s.status_code == 200 else {}
            link = cur
    except HTTPException:
        raise
    except Exception as e:
        return (
            None,
            None,
            {
                "delivered": False,
                "reason": f"Link setup failed for world '{world_name}': {e}",
                "detail": str(e),
            },
        )
    link_info = {
        "connected": bool(link.get("connected")),
        "host": link.get("host"),
        "port": link.get("port"),
        "world": world_name,
        "session_info": link.get("session_info"),
    }
    if not link_info["connected"]:
        return (
            None,
            None,
            {
                "delivered": False,
                "reason": f"Link to world '{world_name}' is not connected.",
                "detail": "Is ResoniteLink enabled in the active session? (Dashboard -> Session -> Settings.)",
                "link": link_info,
            },
        )
    return link_info, world_name, None


def _glb_bbox_m(glb_path: str) -> dict | None:
    """Parse a GLB's JSON chunk for POSITION accessor min/max. Returns metres bbox or None."""
    try:
        import struct as _struct

        with open(glb_path, "rb") as _f:
            _head = _f.read(20)
        if len(_head) < 20:
            return None
        _magic, _ver, _length = _struct.unpack("<III", _head[:12])
        if _magic != 0x46546C67:  # 'glTF'
            return None
        _clen, _ctype = _struct.unpack("<II", _head[12:20])
        with open(glb_path, "rb") as _f:
            _f.seek(20)
            _js = json.loads(_f.read(_clen).decode("utf-8", "replace"))
        _mins: list[list[float]] | None = None
        _maxs: list[list[float]] | None = None
        for _a in _js.get("accessors", []):
            if _a.get("type") == "VEC3" and "min" in _a and "max" in _a:
                _mins = (_mins or []) + [_a["min"]]
                _maxs = (_maxs or []) + [_a["max"]]
        if not _mins or not _maxs:
            return None
        _mn = [min(c[i] for c in _mins) for i in range(3)]
        _mx = [max(c[i] for c in _maxs) for i in range(3)]
        # Skip degenerate unit-cube accessors (Blender default cube): the model
        # bbox is the widest non-trivial VEC3 range.
        return {
            "min": {"x": _mn[0], "y": _mn[1], "z": _mn[2]},
            "max": {"x": _mx[0], "y": _mx[1], "z": _mx[2]},
            "size": {"x": _mx[0] - _mn[0], "y": _mx[1] - _mn[1], "z": _mx[2] - _mn[2]},
            "center": {
                "x": (_mn[0] + _mx[0]) / 2.0,
                "y": (_mn[1] + _mx[1]) / 2.0,
                "z": (_mn[2] + _mx[2]) / 2.0,
            },
        }
    except Exception:
        return None


async def _spawn_glb(
    link_info: dict, world_name: str, glb_path: str, slot_name: str, x: float, y: float, z: float
) -> dict:
    """Spawn one GLB in the connected world. Returns a delivery dict."""
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            u = await client.post(
                _RESONITE_BASE + "/rl/world/spawn-model",
                json={
                    "file_path": os.path.abspath(glb_path),
                    "slot_name": slot_name,
                    "pos_x": x,
                    "pos_y": y,
                    "pos_z": z,
                },
            )
            try:
                uj = u.json()
            except Exception:
                uj = {"status": "error", "message": (u.text or "")[:300]}
    except Exception as e:
        return {
            "delivered": False,
            "reason": f"Spawn request failed: {e}",
            "detail": str(e),
            "link": link_info,
        }
    if u.status_code == 200 and uj.get("status") == "spawned" and uj.get("slot_id"):
        hop = f"{link_info['host']}:{link_info['port']}"
        slot_id = uj["slot_id"]
        bbox = _glb_bbox_m(glb_path)
        verified: bool | None = None
        try:
            async with httpx.AsyncClient(timeout=20) as _vc:
                _v = await _vc.get(_RESONITE_BASE + f"/rl/world/node/{slot_id}")
                verified = _v.status_code == 200
        except Exception:
            verified = None
        if bbox:
            cx = x + bbox["center"]["x"]
            cy = y + bbox["center"]["y"]
            cz = z + bbox["center"]["z"]
            size = bbox["size"]
            detail = (
                f"Spawned '{Path(glb_path).name}' "
                f"({size['x']:.1f} x {size['y']:.1f} x {size['z']:.1f} m) "
                f"in world '{world_name}' as slot '{slot_id}' (name '{slot_name}') "
                f"at ({x}, {y}, {z}) via {hop}. "
                f"Centre approx ({cx:.1f}, {cy:.1f}, {cz:.1f}). "
                f"In Resonite: Inspector search '{slot_name}', double-click to focus; "
                f"you spawn at the corner, the model extends +X / -Z from it. "
                f"Note: the ResoniteLink mesh path ships without a PBS material, "
                f"so walls render unlit grey until you attach one in-game."
            )
        else:
            detail = (
                f"Spawned '{Path(glb_path).name}' in world '{world_name}' as slot '{slot_id}' "
                f"(name '{slot_name}') at ({x}, {y}, {z}) via {hop}. "
                f"In Resonite: Inspector search '{slot_name}', double-click to focus."
            )
        if verified is False:
            detail += " Verification: slot not (yet) visible via /rl/world/node - relog or re-spawn."
        return {
            "delivered": True,
            "detail": detail,
            "link": link_info,
            "spawn": uj,
            "slot_id": slot_id,
            "slot_name": slot_name,
            "bbox_m": bbox,
            "verified": verified,
        }
    msg = uj.get("detail", uj.get("message", "unknown error"))
    return {
        "delivered": False,
        "reason": f"Game client rejected the spawn: {msg}",
        "detail": msg,
        "link": link_info,
        "spawn": uj,
    }


# ── FreeCAD Handoff (fleet cross-connect) ─────────────────────────────────
# Sends qcad STL extrusion output to freecad-mcp for STL→B-Rep solid conversion.
# Requires the freecad-mcp backend running (FreeCAD binary installed). All
# failures surface as 502 with the FreeCAD side's message — never silent.

_FREECAD_BASE = os.environ.get("FREECAD_MCP_URL", "http://127.0.0.1:10944")


@app.get("/api/v1/freecad/status")
async def freecad_status():
    """Probe the freecad-mcp backend for the 3D handoff."""
    for path in ("/api/v1/status", "/api/v1/health"):
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(_FREECAD_BASE + path)
                if r.status_code == 200:
                    return {"reachable": True, "base": _FREECAD_BASE, "status": r.json()}
        except Exception:
            continue
    return {
        "reachable": False,
        "base": _FREECAD_BASE,
        "hint": "Start the freecad-mcp backend (needs FreeCAD installed) to enable STL-to-solid transfer.",
    }


class FreecadSolidRequest(BaseModel):
    stl_name: str = Field(description="STL filename in qcad outputs, e.g. plan.stl")
    output_name: str = Field(default="", description="Optional FCStd name on the FreeCAD side.")


@app.post("/api/v1/freecad/solid")
async def freecad_solid(req: FreecadSolidRequest):
    """Transfer a qcad STL to FreeCAD and convert it to a B-Rep solid (FCStd)."""
    stl_path = os.path.join(OUTPUT_DIR, req.stl_name)
    if not os.path.isfile(stl_path):
        raise HTTPException(404, f"STL '{req.stl_name}' not found in qcad outputs.")
    try:
        with open(stl_path, "rb") as f:
            content = f.read()
        async with httpx.AsyncClient(timeout=120.0) as client:
            up = await client.post(
                _FREECAD_BASE + "/api/v1/upload",
                files={"file": (req.stl_name, content, "application/octet-stream")},
            )
            if up.status_code >= 400:
                raise HTTPException(502, f"FreeCAD upload failed ({up.status_code}): {up.text[:200]}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"FreeCAD backend unreachable at {_FREECAD_BASE}: {e}")
    try:
        args: dict = {"file_name": req.stl_name}
        if req.output_name:
            args["output_name"] = req.output_name
        async with httpx.AsyncClient(timeout=300.0) as client:
            conv = await client.post(
                _FREECAD_BASE + "/api/v1/control/tool",
                json={"tool": "mesh_to_solid", "arguments": args},
            )
            body = conv.json()
    except Exception as e:
        raise HTTPException(502, f"FreeCAD mesh_to_solid call failed: {e}")
    if not body.get("success"):
        raise HTTPException(502, f"FreeCAD mesh_to_solid failed: {body.get('error', body)}")
    out = body.get("output", "")
    return {
        "success": True,
        "output": out,
        "data": body.get("data", {}),
        "download": f"{_FREECAD_BASE}/api/v1/download/{out}" if out else None,
    }


# ── Entry point ──────────────────────────────────────────────────────────────


async def _run_stdio():
    await mcp.run_stdio_async(show_banner=False)


def main():
    import argparse
    import sys as _sys

    _is_tauri = os.environ.get("QCAD_TAURI") == "1" or os.environ.get("QCAD_MCP_TAURI") == "1"
    if _is_tauri:
        try:
            if hasattr(_sys.stdout, "isatty"):
                _sys.stdout.isatty = lambda: False  # type: ignore[method-assign]
            if hasattr(_sys.stderr, "isatty"):
                _sys.stderr.isatty = lambda: False  # type: ignore[method-assign]
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="QCAD MCP Server")
    parser.add_argument("--mode", choices=["stdio", "http", "dual"], default="stdio")
    parser.add_argument("--host", default="0.0.0.0")  # noqa: S104
    parser.add_argument("--port", type=int, default=11966)
    args = parser.parse_args()

    if _is_tauri and args.mode == "stdio":
        logger.warning("QCAD_TAURI=1 set — forcing --mode http (was stdio) to protect sidecar stdout")
        args.mode = "http"
        args.host = os.environ.get("MCP_HOST", args.host)
        args.port = int(os.environ.get("MCP_PORT", str(args.port)))

    if args.mode == "stdio":
        asyncio.run(_run_stdio())
    else:
        logger.info("Starting QCAD MCP on %s:%s", args.host, args.port)
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
