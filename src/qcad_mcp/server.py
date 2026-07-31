"""
FastMCP 3.2 Unified Gateway for QCAD DXF/DWG operations with DWG support and plan_modify.

Architecture:
  DXF/DWG file → ezdxf parser → JSON entities → SVG preview / STL extrusion / room analysis / layer modify.

The server uses ezdxf (pure Python, MIT) for DXF parsing. No external CAD binary required.
QCAD Pro CLI integration (dwg2pdf, dwg2svg, DWG↔DXF conversion) is optional and auto-detected.
"""

import asyncio
import collections
import logging
import os
import subprocess
import time
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile
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
from qcad_mcp.tools import register_all
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
from qcad_mcp.tools.block_tools import plan_blocks, plan_blocks_download
from qcad_mcp.tools.core_tools import (
    plan_analyse,
    plan_create,
    plan_depot,
    plan_export,
    plan_extrude,
    plan_info,
    plan_to_svg,
)
from qcad_mcp.tools.modify_tools import plan_convert, plan_modify
from qcad_mcp.tools.qcad_tools import plan_exec, plan_render, plan_script, qcad_status
from qcad_mcp.tools.script_tools import _SCRIPT_CATEGORIES, plan_scripts_download, plan_scripts_search

logger = logging.getLogger("qcad-mcp")

_START_TIME = time.time()

# ── Lifespan ─────────────────────────────────────────────────────────────────

_state: dict = {}


def _ensure_qcad_running():
    if not qcad_pro.is_installed():
        logger.info("QCAD Pro not installed — skipping auto-start")
        return False
    if qcad_pro.is_running():
        logger.info("QCAD Pro already running")
        return True
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    _state["qcad_pro_ok"] = qcad_pro.is_installed()
    _state["qcad_pro_path"] = str(qcad_pro._qcad_base_dir())
    _ensure_qcad_running()
    _state["qcad_pro_running"] = qcad_pro.is_running()
    _state["qcad_pro_version"] = qcad_pro.get_version()
    _state["depot_dir"] = DEPOT_DIR
    _state["output_dir"] = OUTPUT_DIR
    _state["ezdxf_version"] = _get_ezdxf_version()
    logger.info(
        "QCAD MCP startup — ezdxf %s, QCAD Pro %s (%s), depot: %s",
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
        "http://127.0.0.1:10967",
        "http://localhost:10967",
        "http://goliath:10967",
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
        r = subprocess.run(
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
            cr = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=3)
            if cr.returncode == 0:
                compiler = exe
                break
        except Exception:
            logger.debug("Compiler probe failed for: %s", exe)
            continue
    tool_count = (
        sum(1 for _ in mcp._tool_manager.tools.values()) if hasattr(mcp, "_tool_manager") else len(mcp.get_tools())
    )
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
    tool_count = (
        sum(1 for _ in mcp._tool_manager.tools.values()) if hasattr(mcp, "_tool_manager") else len(mcp.get_tools())
    )
    return {
        "success": True,
        "backend": {"port": 10966, "status": "running", "uptime": int(time.time() - _START_TIME)},
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
    outputs = [
        {"name": f, "size_kb": round(os.path.getsize(os.path.join(OUTPUT_DIR, f)) / 1024, 1)}
        for f in os.listdir(OUTPUT_DIR)
        if os.path.isfile(os.path.join(OUTPUT_DIR, f))
    ]
    return {"uploads": uploads, "outputs": outputs}


# ── REST Endpoints — Tool Bridge ──────────────────────────────────────────────


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
    },
)
_register_tool("plan_export", plan_export, {"file_name": "file_name", "format": "format", "output_name": "output_name"})
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


class ToolRequest(BaseModel):
    tool: str = Field(description=f"Tool name: {', '.join(sorted(_TOOL_DISPATCH.keys()))}")
    arguments: dict = Field(default_factory=dict, description="Tool arguments as a dict")


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
# plan_agentic, plan_transpile, cad_sampling use ctx.sample/request_sampling
# and are only available via MCP protocol, not REST.


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


@app.get("/api/llm/providers")
async def llm_providers():
    models: list[str] = []
    ollama_url = _llm_settings.get("ollama_url", "http://192.168.1.11:11434")
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
    model: str = "gemma3:1b"
    prompt: str = ""


@app.post("/api/llm/chat")
async def llm_chat(req: LlmChatRequest):
    ollama_url = _llm_settings.get("ollama_url", "http://192.168.1.11:11434")
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"{ollama_url}/api/generate",
                json={"model": req.model, "prompt": req.prompt, "stream": False},
            )
            data = r.json()
            return {"response": data.get("response", "")}
    except Exception as e:
        return {"error": str(e)}


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
    return {
        **_llm_settings,
        **_app_settings,
        "qcad_pro_path": _state.get("qcad_pro_path", ""),
        "qcad_pro_ok": _state.get("qcad_pro_ok", False),
    }


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
    return {
        **_llm_settings,
        **_app_settings,
        "qcad_pro_path": _state.get("qcad_pro_path", ""),
        "qcad_pro_ok": _state.get("qcad_pro_ok", False),
    }


@app.post("/api/v1/chat")
async def chat_completion(req: ChatRequest):
    url = req.provider == "ollama" and f"{_llm_settings.get('ollama_url', 'http://192.168.1.11:11434')}/api/chat"
    model = req.model or _llm_settings.get("model", "gemma3:1b")
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
                },
            )
            data = r.json()
            return {"content": (data.get("message") or {}).get("content", "") or data.get("response", "")}
    except Exception as e:
        logger.error("Chat error: %s", e)
        return {"content": f"Error: {e}"}


# ── Entry point ──────────────────────────────────────────────────────────────


async def _run_stdio():
    await mcp.run_stdio_async(show_banner=False)


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
