"""Prefab UI cards for QCAD MCP - rich in-chat surfaces for status/list tools."""

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


async def show_beam_analysis_card(file_name: str = "simple_floorplan.dxf") -> ToolResult:
    """Show 2D beam FEA structural analysis as a rich Prefab card."""
    from qcad_mcp.tools.annotation_tools import plan_beam_analysis

    res = await plan_beam_analysis(
        beams=[{"id": "B1", "length": 5.0, "e_modulus": 210e9, "moment_inertia": 8.33e-6}],
        supports=[{"node": 0, "type": "pinned"}, {"node": 1, "type": "roller"}],
        loads=[{"node": 1, "type": "point", "value": -10000.0}],
    )
    text = f"Beam FEA Analysis: success={res.get('success')}"
    try:
        app = PrefabApp(title="Beam Structural Analysis")
        app.add(Heading(f"FEA Beam Analysis — {file_name}"))
        data = res.get("data", {})
        app.add(Row(label="Max Displacement", value=f"{data.get('max_displacement', 0):.4f} m"))
        app.add(Row(label="Max Shear", value=f"{data.get('max_shear', 0):.2f} N"))
        app.add(Row(label="Max Moment", value=f"{data.get('max_moment', 0):.2f} N*m"))
        return ToolResult(content=text, structured_content=app)
    except Exception as e:
        logger.warning("PrefabApp failed: %s", e)
        return ToolResult(content=text)


async def show_building_meta_card(file_name: str = "simple_floorplan.dxf") -> ToolResult:
    """Show building storeys and level metadata as a rich Prefab card."""
    from qcad_mcp.tools.bim_tools import plan_building_meta

    res = await plan_building_meta(file_name=file_name)
    text = f"Building Storeys: total={res.get('data', {}).get('total_storeys', 0)}"
    try:
        app = PrefabApp(title="Building Storey Metadata")
        app.add(Heading(f"Building Levels — {file_name}"))
        storeys = res.get("data", {}).get("storeys", [])
        for s in storeys:
            app.add(Row(label=s.get("name", "Storey"), value=f"Elev: {s.get('elevation')}mm ({s.get('layer_count')} layers)"))
        return ToolResult(content=text, structured_content=app)
    except Exception as e:
        logger.warning("PrefabApp failed: %s", e)
        return ToolResult(content=text)


def register(mcp):
    mcp.tool(annotations={"readonly": True}, version="0.3.0")(show_qcad_status_card)
    mcp.tool(annotations={"readonly": True}, version="0.3.0")(show_depot_card)
    mcp.tool(annotations={"readonly": True}, version="0.3.0")(show_beam_analysis_card)
    mcp.tool(annotations={"readonly": True}, version="0.3.0")(show_building_meta_card)
