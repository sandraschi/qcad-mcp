"""Prefab UI cards for QCAD MCP — rich in-chat surfaces for status/list tools."""

import logging

from fastmcp.server.server import ToolResult
from prefab_ui import PrefabApp
from prefab_ui.components import Heading, Row

from qcad_mcp.config import DEPOT_DIR
from qcad_mcp.helpers import _depot_list
from qcad_mcp.services import qcad_pro

logger = logging.getLogger("qcad-mcp")


async def show_qcad_status_card() -> ToolResult:
    """Show QCAD Pro installation status as a rich Prefab card.

    ## Return Format
    ToolResult with PrefabApp card, or text summary fallback.

    ## Examples
    await show_qcad_status_card()
    """
    installed = qcad_pro.is_installed()
    running = qcad_pro.is_running()
    version = qcad_pro.get_version() or "not detected"
    install_dir = str(qcad_pro._qcad_base_dir())
    text = f"QCAD Pro: {'installed' if installed else 'not installed'} ({version}), running={running}"
    try:
        app = PrefabApp(title="QCAD Pro Status")
        app.add(Heading("QCAD Pro Status"))
        app.add(Row(label="Installed", value=str(installed)))
        app.add(Row(label="Running", value=str(running)))
        app.add(Row(label="Version", value=version))
        app.add(Row(label="Install Dir", value=install_dir))
        return ToolResult(content=text, structured_content=app)
    except Exception as e:
        logger.warning("PrefabApp failed: %s", e)
        return ToolResult(content=text)


async def show_depot_card() -> ToolResult:
    """Show the CAD file depot contents as a rich Prefab card.

    ## Return Format
    ToolResult with PrefabApp card, or text summary fallback.

    ## Examples
    await show_depot_card()
    """
    files = _depot_list()
    text = f"Depot: {len(files)} files in {DEPOT_DIR}" if files else "Depot is empty"
    try:
        app = PrefabApp(title="CAD File Depot")
        app.add(Heading(f"File Depot ({len(files)} files)"))
        for f in files:
            name = f.get("name", "?")
            size = f.get("size_kb", 0)
            app.add(Row(label=name, value=f"{size:.1f} KB"))
        return ToolResult(content=text, structured_content=app)
    except Exception as e:
        logger.warning("PrefabApp failed: %s", e)
        return ToolResult(content=text)


def register(mcp):
    mcp.tool(annotations={"readonly": True}, version="0.3.0")(show_qcad_status_card)
    mcp.tool(annotations={"readonly": True}, version="0.3.0")(show_depot_card)
