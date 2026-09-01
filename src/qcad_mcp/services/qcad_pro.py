"""
QCAD Pro service - detection, CLI execution, ECMAScript bridge.

Supports three modes:
  1. Headless script execution via qcadcmd.com -no-gui -autostart
  2. High-fidelity rendering via dwg2pdf / dwg2svg
  3. Live instance control via qcad.exe -exec (future)
"""

import json
import logging
import os
import subprocess
import tempfile
import uuid
from pathlib import Path

logger = logging.getLogger("qcad-mcp.qcad_pro")

QCAD_INSTALL_DIR = os.environ.get(
    "QCAD_PRO_PATH",
    os.path.join(os.environ.get("PROGRAMFILES", "C:\\Program Files"), "QCAD"),
)


def _qcad_base_dir() -> Path:
    path = Path(QCAD_INSTALL_DIR)
    if path.is_file():
        path = path.parent
    return path


def _exe(name: str) -> str:
    base = _qcad_base_dir()
    exe = base / name
    return str(exe) if exe.exists() else str(exe) + ".exe" if os.name == "nt" else str(exe)


def is_installed() -> bool:
    """Check if QCAD Pro is installed (binary exists on disk)."""
    return os.path.isfile(_exe("qcadcmd.com")) or os.path.isfile(_exe("qcad.exe"))


def is_running() -> bool:
    """Check if a QCAD Pro GUI instance is currently running."""
    exe_name = "qcad.exe"
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {exe_name}"],
            capture_output=True,
            text=True,
        )
        return exe_name.lower() in result.stdout.lower()
    except Exception:
        return False


def get_version() -> str:
    """Get QCAD Pro version string. Returns empty string if not found."""
    qcad_exe = _exe("qcad.exe")
    if not os.path.isfile(qcad_exe):
        return ""
    try:
        import win32api

        info = win32api.GetFileVersionInfo(qcad_exe, "\\")
        ms = info["FileVersionMS"]
        ls = info["FileVersionLS"]
        return f"{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}"
    except Exception:
        try:
            from win32com.client import Dispatch

            parser = Dispatch("Scripting.FileSystemObject")
            version = parser.GetFileVersion(qcad_exe)
            return version or ""
        except Exception:
            return ""


def cmd() -> str:
    """Return the appropriate QCAD CLI binary path."""
    cmd_exe = _exe("qcadcmd.com")
    if os.path.isfile(cmd_exe):
        return cmd_exe
    return _exe("qcad.exe")


_RENDER_TOOLS = {
    "svg": "dwg2svg.bat",
    "pdf": "dwg2pdf.bat",
    "bmp": "dwg2bmp.bat",
}


def render(input_path: str, output_path: str, fmt: str, timeout: int = 120) -> dict:
    """High-fidelity rendering via QCAD Pro CLI dwg2* tools.

    Uses the QCAD Pro batch files (dwg2svg.bat, dwg2pdf.bat, dwg2bmp.bat)
    for perfect rendering with hatches, TrueType fonts, lineweights, dimensions.

    Args:
        input_path: Absolute path to input DXF/DWG file.
        output_path: Absolute path to output file.
        fmt: Format - "svg", "pdf", or "bmp".
        timeout: Subprocess timeout in seconds.

    Returns:
        {"success": bool, "output": str, "size_kb": float}
    """
    tool = _RENDER_TOOLS.get(fmt)
    if not tool:
        return {"success": False, "error": f"Unknown format: {fmt}. Use svg, pdf, or bmp."}

    tool_path = _qcad_base_dir() / tool
    if not tool_path.exists():
        return {"success": False, "error": f"QCAD Pro tool not found: {tool}"}

    try:
        result = subprocess.run(
            [str(tool_path), "-a", "-f", "-o", output_path, input_path],
            capture_output=True,
            text=True,
            cwd=str(_qcad_base_dir()),
            timeout=timeout,
        )
        if result.returncode != 0 or not os.path.isfile(output_path):
            stderr_tail = result.stderr.split("\n")[-5:] if result.stderr else []
            return {
                "success": False,
                "error": f"QCAD Pro {fmt} render failed (rc={result.returncode})",
                "stderr": stderr_tail,
            }

        size_kb = round(os.path.getsize(output_path) / 1024, 1)
        logger.info(
            "QCAD Pro %s render: %s -> %s (%.1f KB)", fmt, Path(input_path).name, Path(output_path).name, size_kb
        )
        return {"success": True, "output": output_path, "size_kb": size_kb}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"QCAD Pro {fmt} render timed out after {timeout}s."}
    except Exception as e:
        return {"success": False, "error": f"QCAD Pro render error: {e}"}


def convert(input_path: str, output_path: str, fmt: str = "DXF", timeout: int = 120) -> dict:
    """Convert DWG↔DXF using QCAD Pro CLI.

    Args:
        input_path: Absolute path to input file.
        output_path: Absolute path to output file.
        fmt: Target format - "DXF" or "DWG".
        timeout: Subprocess timeout in seconds.

    Returns:
        {"success": bool, "output": str}
    """
    qcad_exe = cmd()
    try:
        result = subprocess.run(
            [
                qcad_exe,
                "-no-gui",
                "-allow-multiple-instances",
                "-autostart",
                "scripts/Pro/Tools/Dwg2Dwg/Dwg2Dwg.js",
                "-f",
                "-o",
                output_path,
                input_path,
            ],
            capture_output=True,
            text=True,
            cwd=str(_qcad_base_dir()),
            timeout=timeout,
        )
        if result.returncode != 0 or not os.path.isfile(output_path):
            return {"success": False, "error": f"Conversion failed (rc={result.returncode})"}
        return {"success": True, "output": output_path}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Conversion timed out after {timeout}s."}
    except Exception as e:
        return {"success": False, "error": f"Conversion error: {e}"}


SCRIPT_TEMPLATE = r"""
// ═══ QCAD MCP Bridge - Auto-Generated ECMAScript ═══
// Session: {session_id}
// Timestamp: {timestamp}
// ═════════════════════════════════════════════════════
qApp.applicationName = "QcadMcpBridge";

var storage = new RMemoryStorage();
var spatialIndex = new RSpatialIndexSimple();
var document = new RDocument(storage, spatialIndex);
var di = new RDocumentInterface(document);

// Import input file if specified
{import_block}

var __mcp = {{}};
var __mcp_errors = [];

try {{
    // ═══ USER CODE ═══
{user_code_indented}
    // ═══ END USER CODE ═══
}} catch (__mcp_e) {{
    __mcp_errors.push("Line " + __mcp_e.lineNumber + ": " + __mcp_e.message);
    if (__mcp_e.stack) {{
        __mcp_errors.push("Stack: " + __mcp_e.stack);
    }}
}}

// Gather output metadata
__mcp.entityCount = document.queryAllEntities().length;
__mcp.layerIds = document.queryAllLayers();
__mcp.layerNames = [];
for (var i = 0; i < __mcp.layerIds.length; i++) {{
    var layer = document.queryLayer(__mcp.layerIds[i]);
    if (layer) __mcp.layerNames.push(layer.getName());
}}

// Export if output path specified
{export_block}

// Print structured result
print("__QCAD_MCP_RESULT__");
print(JSON.stringify({{"session_id":"{session_id}","entity_count":__mcp.entityCount,"layer_count":__mcp.layerIds.length,"layers":__mcp.layerNames,"errors":__mcp_errors,"has_output":{has_output}}}));
""".lstrip()


def run_script(
    user_code: str,
    input_file: str | None = None,
    output_file: str | None = None,
    timeout: int = 120,
) -> dict:
    """Execute ECMAScript against a DXF/DWG via QCAD Pro headless mode.

    Injects user code into a template that creates a document, imports the
    input file (if provided), runs user code, exports output (if requested),
    and returns structured JSON with entity/layer metadata.

    User code runs with `document`, `di`, and full QCAD Qt/ECMAScript API
    available in scope.

    Args:
        user_code: ECMAScript code to execute. Access `document` and `di`.
        input_file: Absolute path to input DXF/DWG (optional).
        output_file: Absolute path to output DXF/DWG (optional).
        timeout: Subprocess timeout in seconds.

    Returns:
        {"success": bool, "data": {"entity_count": int, "layer_count": int,
         "layers": [...], "errors": [...], "output_file": str | None}}
    """
    if not is_installed():
        return {"success": False, "error": "QCAD Pro not installed. Set QCAD_PRO_PATH."}

    session_id = uuid.uuid4().hex[:12]
    timestamp = __import__("datetime").datetime.now().isoformat()

    import_block = ""
    has_output = "false"
    export_block = ""

    if input_file and os.path.isfile(input_file):
        escaped = input_file.replace("\\", "/")
        import_block = f'di.importFile("{escaped}");'
    else:
        import_block = "// No input file - starting from empty document."

    if output_file:
        output_dir = os.path.dirname(output_file)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        escaped = output_file.replace("\\", "/")
        export_block = f'di.exportFile("{escaped}", "DXF 2018");'
        has_output = "true"
    else:
        export_block = "// No output file requested."

    user_code_indented = "\n".join("    " + line for line in user_code.split("\n"))

    script = SCRIPT_TEMPLATE.format(
        session_id=session_id,
        timestamp=timestamp,
        import_block=import_block,
        export_block=export_block,
        has_output=has_output,
        user_code_indented=user_code_indented,
    )

    qcad_exe = _exe("qcad.exe")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(script)
        script_path = f.name

    try:
        result = subprocess.run(
            [qcad_exe, "-no-gui", "-allow-multiple-instances", "-autostart", script_path],
            capture_output=True,
            text=True,
            cwd=str(_qcad_base_dir()),
            timeout=timeout,
        )

        stdout = result.stdout
        stderr = result.stderr

        logger.debug("QCAD script exit=%d, stdout_len=%d, stderr_len=%d", result.returncode, len(stdout), len(stderr))

        data = _parse_script_output(stdout)
        if data is None:
            stderr_tail = stderr.split("\n")[-10:] if stderr else []
            return {"success": False, "error": "QCAD script produced no valid output.", "stderr": stderr_tail}

        data["output_file"] = output_file if has_output == "true" else None
        data["session_id"] = session_id

        if data.get("errors"):
            logger.warning("QCAD script errors: %s", data["errors"])

        return {"success": True, "data": data}

    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"QCAD script timed out after {timeout}s."}
    except Exception as e:
        return {"success": False, "error": f"QCAD script execution failed: {e}"}
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass


def parse_marker(stdout: str, marker: str = "__QCAD_MCP_RESULT__") -> dict | None:
    if marker not in stdout:
        return None
    lines = stdout.split("\n")
    for i, line in enumerate(lines):
        if marker in line and i + 1 < len(lines):
            try:
                return json.loads(lines[i + 1].strip())
            except json.JSONDecodeError:
                return None
    return None


def _parse_script_output(stdout: str) -> dict | None:
    return parse_marker(stdout)


EXEC_TEMPLATE = r"""
// ═══ QCAD MCP Exec - Quick Code Runner ═══
qApp.applicationName = "QcadMcpExec";

var storage = new RMemoryStorage();
var spatialIndex = new RSpatialIndexSimple();
var document = new RDocument(storage, spatialIndex);
var di = new RDocumentInterface(document);

{import_block}

var __mcp = {{}};
var __mcp_errors = [];

try {{
    // ═══ USER CODE ═══
{user_code_indented}
    // ═══ END USER CODE ═══
}} catch (__mcp_e) {{
    __mcp_errors.push("Line " + __mcp_e.lineNumber + ": " + __mcp_e.message);
    if (__mcp_e.stack) __mcp_errors.push("Stack: " + __mcp_e.stack);
}}

__mcp.entityCount = document.queryAllEntities().length;
__mcp.layerIds = document.queryAllLayers();
__mcp.layerNames = [];
for (var i = 0; i < __mcp.layerIds.length; i++) {{
    var layer = document.queryLayer(__mcp.layerIds[i]);
    if (layer) __mcp.layerNames.push(layer.getName());
}}

print("__QCAD_MCP_RESULT__");
print(JSON.stringify({{"entity_count":__mcp.entityCount,"layer_count":__mcp.layerIds.length,"layers":__mcp.layerNames,"errors":__mcp_errors}}));
""".lstrip()


def exec_in_live(
    code: str,
    file_name: str = "",
    timeout: int = 60,
) -> dict:
    """Execute ECMAScript in a temporary QCAD Pro headless session.

    Creates a new document (or loads a depot file), runs user code,
    and returns the entity/layer state. No output file is saved.

    Args:
        code: ECMAScript snippet to execute.
        file_name: Optional depot filename to load first.
        timeout: Subprocess timeout in seconds.

    Returns:
        {"success": bool, "data": {"entity_count": int, "layer_count": int,
         "layers": [...], "errors": [...]}}
    """
    if not is_installed():
        return {"success": False, "error": "QCAD Pro not installed."}

    import_block = ""
    if file_name and os.path.isfile(file_name):
        import_block = f'di.importFile("{file_name.replace(chr(92), "/")}");'
    else:
        import_block = "// Starting from empty document."

    user_code_indented = "\n".join("    " + line for line in code.split("\n"))

    script = EXEC_TEMPLATE.format(
        import_block=import_block,
        user_code_indented=user_code_indented,
    )

    qcad_exe = _exe("qcad.exe")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(script)
        script_path = f.name

    try:
        result = subprocess.run(
            [qcad_exe, "-no-gui", "-allow-multiple-instances", "-autostart", script_path],
            capture_output=True,
            text=True,
            cwd=str(_qcad_base_dir()),
            timeout=timeout,
        )

        data = _parse_script_output(result.stdout)
        if data is None:
            stderr_tail = result.stderr.split("\n")[-5:] if result.stderr else []
            return {"success": False, "error": "Exec produced no valid output.", "stderr": stderr_tail}

        return {"success": True, "data": data, "stdout": result.stdout}

    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Exec timed out after {timeout}s."}
    except Exception as e:
        return {"success": False, "error": f"Exec failed: {e}"}
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass
