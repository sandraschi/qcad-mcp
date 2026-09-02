"""Unit tests for BIM and architectural tools (plan_auto_dimension, plan_building_meta, plan_to_ifc_data)."""

import os
import pytest

from qcad_mcp.tools.bim_tools import plan_auto_dimension, plan_building_meta, plan_to_ifc_data

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
FIXTURE_DXF = os.path.join(FIXTURE_DIR, "simple_floorplan.dxf")


@pytest.mark.asyncio
async def test_plan_auto_dimension():
    res = await plan_auto_dimension(file_name=FIXTURE_DXF, offset=400.0)
    assert res.get("success") is True, f"Auto dimension failed: {res.get('error')}"
    data = res.get("data", {})
    assert data.get("dimension_count") == 4
    assert os.path.exists(data.get("output_path"))


@pytest.mark.asyncio
async def test_plan_building_meta():
    res = await plan_building_meta(file_name=FIXTURE_DXF)
    assert res.get("success") is True, f"Building meta failed: {res.get('error')}"
    data = res.get("data", {})
    assert data.get("total_storeys") >= 1
    assert "storeys" in data


@pytest.mark.asyncio
async def test_plan_to_ifc_data():
    res = await plan_to_ifc_data(file_name=FIXTURE_DXF, wall_height=3000.0)
    assert res.get("success") is True, f"IFC data failed: {res.get('error')}"
    data = res.get("data", {})
    assert "wall_count" in data
    assert "bim_schema" in data
    assert os.path.exists(data.get("ifc_json_path"))
