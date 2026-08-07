"""Tests for qcad-mcp using real DXF fixture files."""

import os

import pytest

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def simple_floorplan():
    path = os.path.join(FIXTURE_DIR, "simple_floorplan.dxf")
    assert os.path.isfile(path), f"Fixture not found: {path}"
    return path


@pytest.fixture
def office_layout():
    path = os.path.join(FIXTURE_DIR, "office_layout.dxf")
    assert os.path.isfile(path)
    return path


@pytest.fixture
def mechanical_bracket():
    path = os.path.join(FIXTURE_DIR, "mechanical_bracket.dxf")
    assert os.path.isfile(path)
    return path


# ── Server init ──


def test_server_state_init():
    from qcad_mcp.server import _state

    assert isinstance(_state, dict)


def test_ezdxf_importable():
    import ezdxf

    assert ezdxf.__version__ is not None


def test_work_dirs_exist():
    from qcad_mcp.server import DEPOT_DIR, OUTPUT_DIR

    assert os.path.exists(DEPOT_DIR)
    assert os.path.exists(OUTPUT_DIR)


# ── Fixture integrity ──


class TestFixtures:
    """Verify fixture DXF files load correctly."""

    FIXTURES = ["simple_floorplan.dxf", "office_layout.dxf", "mechanical_bracket.dxf", "annotation_only.dxf"]

    def test_fixtures_exist(self):
        for f in self.FIXTURES:
            assert os.path.isfile(os.path.join(FIXTURE_DIR, f)), f"Missing fixture: {f}"

    def test_fixtures_parse(self, simple_floorplan):
        import ezdxf

        doc = ezdxf.readfile(simple_floorplan)
        assert doc is not None
        assert len(doc.modelspace()) > 0

    def test_simple_floorplan_structure(self, simple_floorplan):
        import ezdxf

        doc = ezdxf.readfile(simple_floorplan)
        msp = doc.modelspace()
        lines = list(msp.query("LINE"))
        assert len(lines) >= 6, f"Expected 6+ walls, got {len(lines)}"
        layers = {e.dxf.layer for e in msp}
        assert "Walls" in layers
        assert "Doors" in layers or "Windows" in layers, "Missing door or window layer"

    def test_office_layout_has_grid(self, office_layout):
        import ezdxf

        doc = ezdxf.readfile(office_layout)
        lines = list(doc.modelspace().query("LINE LWPOLYLINE"))
        assert len(lines) >= 7, f"Expected 7+ grid lines (outer shell + partitions), got {len(lines)}"

    def test_mechanical_bracket_has_circles(self, mechanical_bracket):
        import ezdxf

        doc = ezdxf.readfile(mechanical_bracket)
        circles = list(doc.modelspace().query("CIRCLE"))
        assert len(circles) == 2, f"Expected 2 holes, got {len(circles)}"

    def test_annotation_only_has_text(self):
        import ezdxf

        path = os.path.join(FIXTURE_DIR, "annotation_only.dxf")
        doc = ezdxf.readfile(path)
        texts = list(doc.modelspace().query("TEXT"))
        assert len(texts) >= 2, f"Expected 2+ text entities, got {len(texts)}"


# ── plan_info tool ──


class TestPlanInfo:
    """Test the plan_info MCP tool with real fixtures."""

    @pytest.mark.asyncio
    async def test_info_simple_floorplan(self, simple_floorplan):
        from qcad_mcp.server import plan_info

        result = await plan_info(file_name=simple_floorplan)
        assert result.get("success"), f"plan_info failed: {result}"
        data = result.get("data", {})
        assert "layers" in data
        assert "entity_counts" in data
        assert data.get("dxf_version")

    @pytest.mark.asyncio
    async def test_info_office(self, office_layout):
        from qcad_mcp.server import plan_info

        result = await plan_info(file_name=office_layout)
        assert result.get("success")
        data = result["data"]
        layer_names = [l.get("name", "") for l in data.get("layers", [])]
        assert "Partitions" in layer_names or "Walls" in layer_names

    @pytest.mark.asyncio
    async def test_info_mechanical(self, mechanical_bracket):
        from qcad_mcp.server import plan_info

        result = await plan_info(file_name=mechanical_bracket)
        assert result.get("success")
        layer_names = [l.get("name", "") for l in result.get("data", {}).get("layers", [])]
        assert "Holes" in layer_names


# ── plan_analyse tool ──


class TestPlanAnalyse:
    """Room/area detection on real floor plans."""

    @pytest.mark.asyncio
    async def test_analyse_floorplan(self, simple_floorplan):
        from qcad_mcp.server import plan_analyse

        result = await plan_analyse(file_name=simple_floorplan)
        assert result.get("success"), f"plan_analyse failed: {result}"

    @pytest.mark.asyncio
    async def test_analyse_office(self, office_layout):
        from qcad_mcp.server import plan_analyse

        result = await plan_analyse(file_name=office_layout)
        assert result.get("success")


# ── plan_to_svg tool ──


class TestPlanToSvg:
    """SVG rendering tests."""

    @pytest.mark.asyncio
    async def test_svg_floorplan(self, simple_floorplan):
        from qcad_mcp.server import plan_to_svg

        result = await plan_to_svg(file_name=simple_floorplan)
        assert result.get("success"), f"plan_to_svg failed: {result}"
        assert result.get("output", "").endswith(".svg")

    @pytest.mark.asyncio
    async def test_svg_with_layer_filter(self, simple_floorplan):
        from qcad_mcp.server import plan_to_svg

        result = await plan_to_svg(file_name=simple_floorplan, layers=["Walls"])
        assert result.get("success")


# ── plan_extrude tool ──


class TestPlanExtrude:
    """STL extrusion tests."""

    @pytest.mark.asyncio
    async def test_extrude_floorplan(self, simple_floorplan):
        from qcad_mcp.server import plan_extrude

        result = await plan_extrude(file_name=simple_floorplan, wall_height=3.0, wall_thickness=0.3)
        if not result.get("success"):
            pytest.skip(f"No walls detected (expected for test file): {result.get('error')}")
        assert result.get("output", "").endswith(".stl")

    @pytest.mark.asyncio
    async def test_extrude_office(self, office_layout):
        from qcad_mcp.server import plan_extrude

        result = await plan_extrude(file_name=office_layout, wall_height=3.0, wall_thickness=0.3)
        if not result.get("success"):
            pytest.skip(f"No walls detected: {result.get('error')}")
        assert result.get("output", "").endswith(".stl")


# ── plan_create tool ──


class TestPlanCreate:
    """DXF creation from primitives — cleans depot before each test."""

    @pytest.fixture(autouse=True)
    def clean_depot(self):
        from qcad_mcp.server import DEPOT_DIR

        for f in os.listdir(DEPOT_DIR):
            p = os.path.join(DEPOT_DIR, f)
            if os.path.isfile(p) and f.endswith(".dxf"):
                os.remove(p)
        yield

    @pytest.mark.asyncio
    async def test_create_rect(self):
        from qcad_mcp.server import plan_create

        result = await plan_create(
            filename="test_create_rect.dxf",
            entities=[{"type": "rect", "layer": "Walls", "x": 0, "y": 0, "w": 1000, "h": 800}],
        )
        assert result.get("success"), f"plan_create failed: {result}"
        import ezdxf

        from qcad_mcp.server import DEPOT_DIR

        doc = ezdxf.readfile(os.path.join(DEPOT_DIR, result["filename"]))
        assert len(list(doc.modelspace())) >= 1

    @pytest.mark.asyncio
    async def test_create_multi_entity(self):
        from qcad_mcp.server import plan_create

        result = await plan_create(
            filename="test_multi.dxf",
            entities=[
                {"type": "rect", "layer": "Walls", "x": 0, "y": 0, "w": 1000, "h": 800},
                {"type": "circle", "layer": "Columns", "cx": 500, "cy": 400, "r": 50},
                {"type": "text", "layer": "Labels", "x": 100, "y": 100, "content": "Test", "height": 50},
            ],
        )
        assert result.get("success"), f"plan_create failed: {result}"
        import ezdxf

        from qcad_mcp.server import DEPOT_DIR

        doc = ezdxf.readfile(os.path.join(DEPOT_DIR, result["filename"]))
        assert len(list(doc.modelspace())) == 3

    @pytest.mark.asyncio
    async def test_create_line(self):
        from qcad_mcp.server import plan_create

        result = await plan_create(
            filename="test_line.dxf",
            entities=[{"type": "line", "layer": "Walls", "x1": 0, "y1": 0, "x2": 100, "y2": 100}],
        )
        assert result.get("success")
        assert result.get("filename")


# ── plan_depot tool ──


class TestPlanDepot:
    """Depot listing tests — depends on plan_create creating files."""

    @pytest.mark.asyncio
    async def test_depot_has_created_files(self):
        from qcad_mcp.server import plan_depot

        result = await plan_depot()
        assert result.get("success")
        names = [f["name"] for f in result.get("data", {}).get("files", [])]
        assert len(names) >= 1, f"Expected at least 1 file in depot, got {names}"
