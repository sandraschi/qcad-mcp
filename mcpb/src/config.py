"""QCAD MCP configuration constants and directory bootstrapping."""

import os

QCAD_PRO_PATH = os.environ.get(
    "QCAD_PRO_PATH",
    os.path.join(os.environ.get("PROGRAMFILES", "C:\\Program Files"), "QCAD", "qcad.exe"),
)
DEPOT_DIR = os.environ.get(
    "QCAD_MCP_DEPOT",
    os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "qcad-mcp", "depot"),
)
OUTPUT_DIR = os.environ.get(
    "QCAD_MCP_OUTPUT",
    os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "qcad-mcp", "output"),
)
os.makedirs(DEPOT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

EXT_DXF = {".dxf", ".dwg"}
