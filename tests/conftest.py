"""Shared test fixtures and configuration for qcad-mcp."""

import os
import sys
import tempfile
from pathlib import Path

# Isolate file-system side effects BEFORE qcad_mcp.config binds its paths:
# the suite must never touch the live depot/outputs under %LOCALAPPDATA%.
_TEST_ROOT = tempfile.mkdtemp(prefix="qcad-mcp-tests-")
os.environ["QCAD_MCP_DEPOT"] = os.path.join(_TEST_ROOT, "depot")
os.environ["QCAD_MCP_OUTPUT"] = os.path.join(_TEST_ROOT, "output")
# Same for persisted settings (server reads these at import): the suite must
# neither see the user's selected model nor overwrite their settings file.
os.environ["QCAD_SETTINGS_FILE"] = os.path.join(_TEST_ROOT, "settings.json")

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture(scope="session")
def fixture_dir():
    return FIXTURE_DIR
