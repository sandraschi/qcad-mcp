"""Tests for plan_transpile — AutoLISP to ECMAScript transpiler."""

import os

import pytest

from qcad_mcp.tools.agentic_tools import _heuristic_transpile, plan_transpile

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

LISP_FIXTURES = [
    "draw_line.lsp",
    "draw_circle.lsp",
    "draw_rect_defun.lsp",
    "entity_count.lsp",
    "array_grid.lsp",
    "dimension_linear.lsp",
    "layer_create.lsp",
    "complex_floorplan.lsp",
]


def _read_fixture(name: str) -> str:
    path = os.path.join(FIXTURE_DIR, name)
    with open(path) as f:
        return f.read()


class TestHeuristicTranspile:
    """Test heuristic (no AI) transpilation of common AutoLISP patterns."""

    def test_transpile_line(self):
        lisp = _read_fixture("draw_line.lsp")
        js = _heuristic_transpile(lisp)
        assert "RLineEntity" in js
        assert "RLineData" in js
        assert "RVector(0,0)" in js
        assert "RVector(100,50)" in js

    def test_transpile_circle(self):
        lisp = _read_fixture("draw_circle.lsp")
        js = _heuristic_transpile(lisp)
        assert "RCircleEntity" in js
        assert "RCircleData" in js
        assert "RVector(50,25)" in js
        assert "20" in js

    def test_transpile_rect_defun(self):
        lisp = _read_fixture("draw_rect_defun.lsp")
        js = _heuristic_transpile(lisp)
        assert "RLineEntity" in js
        assert "var w = 100" in js
        assert "var h = 80" in js
        assert "RVector(0,0)" in js
        assert "RVector(w,0)" in js

    def test_transpile_dimension(self):
        lisp = _read_fixture("dimension_linear.lsp")
        js = _heuristic_transpile(lisp)
        # Heuristic fallback for unrecognized patterns
        assert len(js) > 50
        assert "AutoLISP" in js or "op = new RAddObjectsOperation" in js

    def test_transpile_unknown_fallback(self):
        lisp = _read_fixture("entity_count.lsp")
        js = _heuristic_transpile(lisp)
        # Should produce fallback placeholder
        assert "AutoLISP" in js or "heuristic" in js.lower()
        assert "RAddObjectsOperation" in js  # always produces valid structure

    def test_transpile_grid_loop(self):
        lisp = _read_fixture("array_grid.lsp")
        js = _heuristic_transpile(lisp)
        assert len(js) > 50
        # Complex loop patterns get fallback
        assert "RAddObjectsOperation" in js

    def test_transpile_layer_creation(self):
        lisp = _read_fixture("layer_create.lsp")
        js = _heuristic_transpile(lisp)
        assert len(js) > 50
        assert "RAddObjectsOperation" in js

    def test_transpile_complex_floorplan(self):
        lisp = _read_fixture("complex_floorplan.lsp")
        js = _heuristic_transpile(lisp)
        assert len(js) > 100
        assert "RAddObjectsOperation" in js
        # Complex multi-step should still produce valid structure
        assert "op.apply(document)" in js

    def test_transpile_empty_input(self):
        assert _heuristic_transpile("") == ""
        assert _heuristic_transpile("   ") == ""

    def test_all_fixtures_produce_valid_js(self):
        for name in LISP_FIXTURES:
            lisp = _read_fixture(name)
            js = _heuristic_transpile(lisp)
            assert js, f"Fixture {name} produced empty output"
            assert "op.apply(document)" in js or "AutoLISP" in js, (
                f"Fixture {name} missing apply or fallback marker"
            )


@pytest.mark.asyncio
class TestTranspileExecution:
    """Test full transpile + execute pipeline (requires QCAD Pro)."""

    @pytest.mark.skipif(
        not os.environ.get("QCAD_PRO_PATH")
        and not os.path.isfile(
            os.path.join(
                os.environ.get("PROGRAMFILES", "C:\\Program Files"),
                "QCAD",
                "qcad.exe",
            )
        ),
        reason="QCAD Pro not installed",
    )
    async def test_transpile_line_execute(self):
        lisp = _read_fixture("draw_line.lsp")
        result = await plan_transpile(
            lisp_code=lisp,
            output_name="test_transpile_line.dxf",
        )
        assert result.get("success"), f"Transpile failed: {result.get('error')}"
        data = result.get("data", {})
        assert data.get("entity_count", 0) >= 1
        assert "transpiled_js" in data
        assert "original_lisp" in data

    @pytest.mark.skipif(
        not os.environ.get("QCAD_PRO_PATH")
        and not os.path.isfile(
            os.path.join(
                os.environ.get("PROGRAMFILES", "C:\\Program Files"),
                "QCAD",
                "qcad.exe",
            )
        ),
        reason="QCAD Pro not installed",
    )
    async def test_transpile_circle_execute(self):
        lisp = _read_fixture("draw_circle.lsp")
        result = await plan_transpile(
            lisp_code=lisp,
            output_name="test_transpile_circle.dxf",
        )
        assert result.get("success"), f"Transpile failed: {result.get('error')}"
        assert result.get("data", {}).get("entity_count", 0) >= 1

    @pytest.mark.skipif(
        not os.environ.get("QCAD_PRO_PATH")
        and not os.path.isfile(
            os.path.join(
                os.environ.get("PROGRAMFILES", "C:\\Program Files"),
                "QCAD",
                "qcad.exe",
            )
        ),
        reason="QCAD Pro not installed",
    )
    async def test_transpile_rect_execute(self):
        lisp = _read_fixture("draw_rect_defun.lsp")
        result = await plan_transpile(
            lisp_code=lisp,
            output_name="test_transpile_rect.dxf",
        )
        assert result.get("success"), f"Transpile failed: {result.get('error')}"
        # Rectangle = 4 lines
        assert result.get("data", {}).get("entity_count", 0) == 4

    @pytest.mark.skipif(
        not os.environ.get("QCAD_PRO_PATH")
        and not os.path.isfile(
            os.path.join(
                os.environ.get("PROGRAMFILES", "C:\\Program Files"),
                "QCAD",
                "qcad.exe",
            )
        ),
        reason="QCAD Pro not installed",
    )
    async def test_transpile_source_tracking(self):
        lisp = _read_fixture("draw_line.lsp")
        result = await plan_transpile(
            lisp_code=lisp,
            output_name="test_transpile_source.dxf",
        )
        data = result.get("data", {})
        source = data.get("source", "")
        assert source in ("heuristic", "ai_transpiler")
