"""Prefab UI cards for QCAD MCP - rich in-chat surfaces for status/list tools."""

import asyncio
import logging
from typing import Any

from fastmcp.tools.base import ToolResult
from prefab_ui import PrefabApp
from prefab_ui.components import Column, Component, Heading, Row, Text

from qcad_mcp.config import DEPOT_DIR
from qcad_mcp.helpers import _depot_list
from qcad_mcp.services import qcad_pro

logger = logging.getLogger("qcad-mcp")


def _kv(label: str, value: str) -> Component:
    """Single label/value line for card bodies."""
    return Row(children=[Text(content=f"{label}: {value}")])


def _card(title: str, heading: str, rows: list[str]) -> PrefabApp:
    """Compose a simple heading + key/value-line card."""
    return PrefabApp(
        title=title,
        view=Column(children=[Heading(heading), *(Text(content=r) for r in rows)]),
    )


async def show_qcad_status_card() -> ToolResult:
    """Show QCAD Pro installation status as a rich Prefab card.

    ## Return Format
    ToolResult with PrefabApp card, or text summary fallback.

    ## Examples
    await show_qcad_status_card()
    """
    installed = qcad_pro.is_installed()
    running = await asyncio.to_thread(qcad_pro.is_running)
    version = qcad_pro.get_version() or "not detected"
    install_dir = str(qcad_pro._qcad_base_dir())
    text = f"QCAD Pro: {'installed' if installed else 'not installed'} ({version}), running={running}"
    try:
        app = _card(
            "QCAD Pro Status",
            "QCAD Pro Status",
            [
                f"Installed: {installed}",
                f"Running: {running}",
                f"Version: {version}",
                f"Install Dir: {install_dir}",
            ],
        )
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
    files: list[dict[str, Any]] = _depot_list()
    text = f"Depot: {len(files)} files in {DEPOT_DIR}" if files else "Depot is empty"
    try:
        rows = [f"{f.get('name', '?')}: {float(f.get('size_kb', 0)):.1f} KB" for f in files]
        app = _card("CAD File Depot", f"File Depot ({len(files)} files)", rows)
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
    data: dict[str, Any] = res.get("data", {})
    text = f"Beam FEA Analysis: success={res.get('success')}"
    try:
        app = _card(
            "Beam Structural Analysis",
            f"FEA Beam Analysis — {file_name}",
            [
                f"Max Displacement: {float(data.get('max_displacement', 0)):.4f} m",
                f"Max Shear: {float(data.get('max_shear', 0)):.2f} N",
                f"Max Moment: {float(data.get('max_moment', 0)):.2f} N*m",
            ],
        )
        return ToolResult(content=text, structured_content=app)
    except Exception as e:
        logger.warning("PrefabApp failed: %s", e)
        return ToolResult(content=text)


async def show_building_meta_card(file_name: str = "simple_floorplan.dxf") -> ToolResult:
    """Show building storeys and level metadata as a rich Prefab card."""
    from qcad_mcp.tools.bim_tools import plan_building_meta

    res = await plan_building_meta(file_name=file_name)
    payload: dict[str, Any] = res.get("data", {})
    text = f"Building Storeys: total={payload.get('total_storeys', 0)}"
    try:
        storeys: list[dict[str, Any]] = payload.get("storeys", [])
        rows = [
            f"{s.get('name', 'Storey')}: Elev {s.get('elevation')}mm ({s.get('layer_count')} layers)" for s in storeys
        ]
        app = _card("Building Storey Metadata", f"Building Levels — {file_name}", rows)
        return ToolResult(content=text, structured_content=app)
    except Exception as e:
        logger.warning("PrefabApp failed: %s", e)
        return ToolResult(content=text)


def register(mcp):
    mcp.tool(annotations={"readonly": True}, version="0.5.0")(show_qcad_status_card)
    mcp.tool(annotations={"readonly": True}, version="0.5.0")(show_depot_card)
    mcp.tool(annotations={"readonly": True}, version="0.5.0")(show_beam_analysis_card)
    mcp.tool(annotations={"readonly": True}, version="0.5.0")(show_building_meta_card)
