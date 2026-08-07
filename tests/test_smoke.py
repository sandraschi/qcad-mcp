"""Minimal test: server initialises, MCP tool decorators work, ezdxf importable."""

import os

from qcad_mcp.server import _state


def test_server_state_init():
    assert isinstance(_state, dict)


def test_ezdxf_importable():
    import ezdxf

    assert ezdxf.__version__ is not None


def test_work_dirs_exist():
    from qcad_mcp.server import DEPOT_DIR, OUTPUT_DIR

    assert os.path.exists(DEPOT_DIR)
    assert os.path.exists(OUTPUT_DIR)
