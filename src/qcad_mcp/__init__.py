"""
QCAD MCP - DXF/DWG floor plan operations via FastMCP 3.2 Unified Gateway.

Provides programmatic access to DXF/DWG files for preview, analysis,
extrusion, and export. Powered by ezdxf (pure Python, MIT license).

Exports:
    plan_info - layers, entities, bounding box metadata
    plan_to_svg - DXF to SVG preview
    plan_extrude - DXF walls to STL 3D mesh
    plan_export - DXF to PDF/image export
    plan_analyse - room detection, area, wall lengths
"""

from __future__ import annotations

import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("qcad-mcp")
