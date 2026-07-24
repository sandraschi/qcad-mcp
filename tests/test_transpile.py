"""Tests for plan_transpile — AutoLISP to ECMAScript transpiler.

These test actual translation correctness (specific entity types, coordinates,
counts), not just "did the function return non-empty text without throwing."
The previous version of this file accepted the untranslated fallback
placeholder as a pass for 6 of 8 fixtures, because its assertion
(`"AutoLISP" in js or "op = new RAddObjectsOperation" in js`) matched the
placeholder's own boilerplate text regardless of whether real translation
happened.
"""

import os

import pytest

from qcad_mcp.tools.agentic_tools import plan_transpile
from qcad_mcp.tools.lisp_transpiler import transpile as _heuristic_transpile

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
    """Test heuristic (no AI) transpilation of common AutoLISP patterns.

    Every assertion here checks for a specific, correct translated value —
    an exact coordinate, entity type, or count — not just "some output was
    produced."
    """

    def test_transpile_line(self):
        lisp = _read_fixture("draw_line.lsp")
        js = _heuristic_transpile(lisp)
        assert "RLineEntity" in js
        assert "RLineData" in js
        assert "RVector(0,0)" in js
        assert "RVector(100,50)" in js
        assert "UNRECOGNIZED" not in js

    def test_transpile_circle(self):
        lisp = _read_fixture("draw_circle.lsp")
        js = _heuristic_transpile(lisp)
        assert "RCircleEntity" in js
        assert "RCircleData" in js
        assert "RVector(50,25)" in js
        assert ", 20)" in js  # radius, not just the substring "20" anywhere
        assert "UNRECOGNIZED" not in js

    def test_transpile_rect_defun(self):
        """The rect is defined via a (defun draw-rect (w h) ...) called with
        (draw-rect 100 80) — this exercises defun-parameter substitution,
        not just literal-argument command translation."""
        lisp = _read_fixture("draw_rect_defun.lsp")
        js = _heuristic_transpile(lisp)
        assert js.count("RLineEntity") == 4, "a rectangle is exactly 4 lines"
        assert "RVector(0,0)" in js
        assert "RVector(100,0)" in js
        assert "RVector(100,80)" in js
        assert "RVector(0,80)" in js
        assert "UNRECOGNIZED" not in js

    def test_transpile_dimension(self):
        """(defun c:dim-walls (pt1 pt2 pt3) ...) called with 3 point args —
        exercises multi-parameter defun substitution into a DIMLINEAR."""
        lisp = _read_fixture("dimension_linear.lsp")
        js = _heuristic_transpile(lisp)
        assert "RDimAlignedEntity" in js
        assert "RVector(0,0)" in js
        assert "RVector(5000,0)" in js
        assert "RVector(2500,-500)" in js
        assert "UNRECOGNIZED" not in js

    def test_transpile_entity_count(self):
        """This fixture has no drawing side effects at all (ssget + sslength
        + princ, purely informational) — the correct translation queries the
        document and prints a count, and adds NO new geometry. The old
        version silently no-op'd this into an empty RAddObjectsOperation,
        which happened to "pass" but wasn't actually a translation of
        anything the AutoLISP does."""
        lisp = _read_fixture("entity_count.lsp")
        js = _heuristic_transpile(lisp)
        assert "document.queryAllEntities()" in js
        assert "ss.length" in js
        assert "Total entities" in js
        # No geometry should be created — this script only counts and prints.
        assert "RAddObjectsOperation" not in js
        assert "UNRECOGNIZED" not in js

    def test_transpile_grid_loop(self):
        """Nested (repeat 5 (repeat 4 ...)) with (setq x (+ x 100)) increments.
        The bounds and increments are all compile-time literals, so this
        should fully unroll into 5*4*2 = 40 real RLineEntity calls with
        correct coordinates — not a placeholder."""
        lisp = _read_fixture("array_grid.lsp")
        js = _heuristic_transpile(lisp)
        assert js.count("RLineEntity") == 40, "5 x 4 grid x 2 lines per cell"
        # spot-check the first and last cell coordinates
        assert "RVector(0,0)" in js
        assert "RVector(400,300)" in js  # last outer/inner iteration start point
        assert "UNRECOGNIZED" not in js

    def test_transpile_layer_creation(self):
        """Three (command "_LAYER" "N" name "C" color ...) calls should
        produce three distinct RLayer objects with the right names and
        colors, in their own operation (not mixed into geometry, and not
        referencing an undeclared `op2`)."""
        lisp = _read_fixture("layer_create.lsp")
        js = _heuristic_transpile(lisp)
        assert "var op2 = new RAddObjectsOperation();" in js
        assert "op2.apply(document);" in js
        assert 'RLayer(document, "Walls", false, false, new RColor(1))' in js
        assert 'RLayer(document, "Doors", false, false, new RColor(3))' in js
        assert 'RLayer(document, "Furniture", false, false, new RColor(5))' in js
        assert "UNRECOGNIZED" not in js

    def test_transpile_complex_floorplan(self):
        """Multi-command real-world script: 5 walls, 1 column, 1 door arc,
        2 labels, 2 dimensions. Every one of these should translate to a
        real, correctly-typed entity — this is the fixture that most
        resembles what someone would actually paste in."""
        lisp = _read_fixture("complex_floorplan.lsp")
        js = _heuristic_transpile(lisp)
        assert js.count("RLineEntity") == 5
        assert js.count("RCircleEntity") == 1
        assert js.count("RArcEntity") == 1
        assert js.count("RTextEntity") == 2
        assert js.count("RDimAlignedEntity") == 2
        assert "'Living Room'" in js
        assert "'Bedroom'" in js
        assert "UNRECOGNIZED" not in js

    def test_transpile_empty_input(self):
        assert _heuristic_transpile("") == ""
        assert _heuristic_transpile("   ") == ""

    def test_transpile_unrecognized_construct_is_marked_honestly(self):
        """A genuinely unsupported AutoLISP construct (OFFSET/EXPLODE — no
        QCAD equivalent modeled) must be marked inline as unrecognized,
        not silently swallowed into a no-op that looks like success."""
        lisp = """
        (defun c:weird ()
          (command "_EXPLODE" (entlast))
          (command "_OFFSET" 50 (entlast) (list 10 10) "")
        )
        (c:weird)
        """
        js = _heuristic_transpile(lisp)
        assert "UNRECOGNIZED" in js
        assert "_EXPLODE" in js
        assert "_OFFSET" in js

    def test_all_fixtures_translate_without_warnings(self):
        """None of the 8 real fixtures should hit the unrecognized-construct
        path — they're all supposed to be within what this heuristic engine
        handles. If this starts failing after a fixture changes, that's a
        signal the heuristic needs extending, not that the test should be
        loosened to accept the fallback again."""
        for name in LISP_FIXTURES:
            lisp = _read_fixture(name)
            js = _heuristic_transpile(lisp)
            assert js, f"Fixture {name} produced empty output"
            assert "UNRECOGNIZED" not in js, f"Fixture {name} hit the fallback path"


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
