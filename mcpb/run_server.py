"""Entry point for PyInstaller-bundled server — Gate J isatty shim + Tauri guard."""

import _strptime  # noqa: F401
import logging
import os
import sys

logger = logging.getLogger("qcad-mcp.run")

sys.path.insert(0, ".")

if os.environ.get("QCAD_TAURI") == "1" or os.environ.get("QCAD_MCP_TAURI") == "1":
    try:
        if hasattr(sys.stdout, "isatty"):
            sys.stdout.isatty = lambda: False  # type: ignore[method-assign]
        if hasattr(sys.stderr, "isatty"):
            sys.stderr.isatty = lambda: False  # type: ignore[method-assign]
    except Exception as e:
        logger.debug("isatty shim failed: %s", e)

from qcad_mcp.server import main


def _configure_transport_argv() -> None:
    """Force HTTP argv when a sidecar env demands it. Import-safe: only
    rewrites sys.argv, never starts the server (pack-time runpy check)."""
    is_tauri = os.environ.get("QCAD_TAURI") == "1" or os.environ.get("QCAD_MCP_TAURI") == "1"
    port = os.environ.get("MCP_PORT") or os.environ.get("PORT")
    if is_tauri and not port:
        port = "11966"
    if port:
        host = os.environ.get("MCP_HOST", "127.0.0.1")
        sys.argv = ["run_server.py", "--mode", "http", "--host", host, "--port", str(port)]
    elif is_tauri:
        sys.argv = ["run_server.py", "--mode", "http", "--host", "127.0.0.1", "--port", "11966"]


if __name__ == "__main__":
    _configure_transport_argv()
    main()
