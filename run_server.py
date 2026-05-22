"""Entry point for PyInstaller-bundled server."""
import sys

sys.path.insert(0, ".")

from qcad_mcp.server import main

main()
