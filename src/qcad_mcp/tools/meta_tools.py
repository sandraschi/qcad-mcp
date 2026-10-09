"""Meta tools: live help catalog + orderly self-termination."""

import logging
import os
import threading
from typing import Annotated

from pydantic import Field

logger = logging.getLogger("qcad-mcp")

_READ_ONLY = {"readonly": True}


async def qcad_help(
    topic: Annotated[str, Field(default="", description="Filter tools by name substring, e.g. 'extrude'.")] = "",
) -> dict:
    """List server capabilities: MCP tools, REST routes, and config.

    Start here when you do not know which tool fits. Returns the tool
    catalog (40 ops across 9 modules), key REST endpoints, ports, and env
    vars. Filter with `topic` for a focused subset.

    ## Return Format
    {"success": bool, "data": {"tools": [...], "rest": [...], "config": {...}}}

    ## Examples
    await qcad_help()
    await qcad_help(topic="extrude")
    """
    from qcad_mcp import server as _srv

    tools = sorted(
        getattr(t, "name", "?") for t in await _srv.mcp.list_tools() if not topic or topic in getattr(t, "name", "")
    )
    return {
        "success": True,
        "data": {
            "tools": tools,
            "rest": [
                "GET /api/v1/health",
                "GET /api/v1/status",
                "GET /api/v1/diagnostics",
                "GET /api/skills",
                "POST /api/v1/control/tool",
                "POST /api/shutdown",
            ],
            "config": {
                "backend_port": 11966,
                "frontend_port": 11967,
                "docs": "docs/TOOLS.md",
                "skill": "skills/qcad-cad/SKILL.md",
            },
        },
    }


async def qcad_shutdown(
    confirm: Annotated[bool, Field(description="Must be true — guards against accidental shutdown.")] = False,
) -> dict:
    """Shut the QCAD MCP server down gracefully (orderly exit).

    Responds first, then exits the process ~500 ms later so in-flight writes
    (depot sidecars, settings) can flush. The fleet launcher calls
    POST /api/shutdown before service restarts for the same reason.

    ## Return Format
    {"success": bool, "message": str}

    ## Examples
    await qcad_shutdown(confirm=True)
    """
    if not confirm:
        return {"success": False, "message": "Pass confirm=True to shut down."}
    logger.warning("qcad_shutdown requested — exiting in 0.5 s")
    threading.Timer(0.5, lambda: os._exit(0)).start()
    return {"success": True, "message": "Shutting down in 0.5 s."}


def register(mcp):
    mcp.tool(annotations=_READ_ONLY, version="0.3.0")(qcad_help)
    mcp.tool(annotations=_READ_ONLY, version="0.3.0")(qcad_shutdown)
