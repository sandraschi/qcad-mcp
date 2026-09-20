"""Tests for LLM floor-plan generation (services/plan_llm + REST endpoint).

Pure unit tests for JSON extraction and entity validation (no Ollama needed)
plus endpoint tests with the Ollama call monkeypatched out.
"""

import os

import pytest
from fastapi.testclient import TestClient

import qcad_mcp.server as srv
from qcad_mcp.services import plan_llm
from qcad_mcp.tools import agentic_tools


@pytest.fixture(scope="module")
def client():
    return TestClient(srv.app)


class TestExtract:
    def test_plain_object(self):
        assert plan_llm.extract_plan_json('{"entities": []}') == {"entities": []}

    def test_fenced(self):
        raw = '```json\n{"entities": [{"type": "rect"}]}\n```'
        assert plan_llm.extract_plan_json(raw)["entities"][0]["type"] == "rect"

    def test_prose_wrapped(self):
        raw = 'Here is your plan:\n{"entities": []}\nGood luck!'
        assert plan_llm.extract_plan_json(raw) == {"entities": []}

    def test_no_json(self):
        with pytest.raises(plan_llm.PlanLlmError) as e:
            plan_llm.extract_plan_json("no braces here")
        assert e.value.code == "json"

    def test_bad_json(self):
        with pytest.raises(plan_llm.PlanLlmError) as e:
            plan_llm.extract_plan_json('{"entities": [}')
        assert e.value.code == "json"


class TestValidateSingle:
    def test_good_plan(self):
        data = {
            "entities": [
                {"type": "rect", "x1": 0, "y1": 0, "x2": 6000, "y2": 5000, "layer": "Walls"},
                {"type": "door", "x": 2700, "y": 0, "w": 900, "angle": 0, "layer": "Doors"},
                {"type": "text", "x": 1000, "y": 2500, "h": 300, "text": "ROOM 1", "layer": "Text"},
            ],
            "layers": [{"name": "Walls", "color": 7}],
        }
        spec, warnings = plan_llm.validate_plan(data)
        assert warnings == []
        assert len(spec["entities"]) == 3
        assert {layer["name"] for layer in spec["layers"]} >= {"Walls", "Doors", "Text"}

    def test_drops_invalid_keeps_valid(self):
        data = {
            "entities": [
                {"type": "rect", "x1": 0, "y1": 0, "x2": 6000, "y2": 5000},
                {"type": "teleporter", "x": 1, "y": 2},
                {"type": "line", "x1": 0},
                {"type": "circle", "x": 0, "y": 0, "r": -5},
                {"type": "text", "x": 0, "y": 0, "text": "   "},
                {"type": "rect", "x1": 0, "y1": 0, "x2": 99999999, "y2": 10},
            ]
        }
        spec, warnings = plan_llm.validate_plan(data)
        assert len(spec["entities"]) == 1
        assert spec["entities"][0]["layer"] == "Walls"  # default layer assigned
        assert any("5" in w for w in warnings)

    def test_empty_raises(self):
        with pytest.raises(plan_llm.PlanLlmError) as e:
            plan_llm.validate_plan({"entities": []})
        assert e.value.code == "plan"

    def test_all_invalid_raises(self):
        with pytest.raises(plan_llm.PlanLlmError) as e:
            plan_llm.validate_plan({"entities": [{"type": "nope"}]})
        assert e.value.code == "plan"


class TestValidateLevels:
    def test_good_tower(self):
        data = {
            "levels": [
                {
                    "suffix": "L0",
                    "title": "Ground",
                    "elevation": 0,
                    "entities": [{"type": "rect", "x1": 0, "y1": 0, "x2": 30000, "y2": 12000}],
                    "inserts": [],
                },
                {
                    "suffix": "L1",
                    "title": "Up",
                    "elevation": 3.5,
                    "entities": [{"type": "rect", "x1": 0, "y1": 0, "x2": 30000, "y2": 12000}],
                    "inserts": [{"block_name": "bed", "x": 1000, "y": 1000}],
                },
            ]
        }
        spec, _ = plan_llm.validate_plan(data)
        assert len(spec["levels"]) == 2
        assert spec["levels"][1]["elevation"] == 3.5
        assert spec["levels"][1]["inserts"][0]["block_name"] == "BED"

    def test_empty_levels_raises(self):
        with pytest.raises(plan_llm.PlanLlmError):
            plan_llm.validate_plan({"levels": [{"suffix": "L0", "entities": [{"type": "nope"}]}]})


class TestEndpoint:
    def test_no_model_refuses(self, client, monkeypatch):
        monkeypatch.setattr(srv, "_llm_settings", {"ollama_url": "http://127.0.0.1:11434", "model": ""})
        r = client.post("/api/v1/ai/generate-plan", json={"goal": "shed 3m x 2m"})
        body = r.json()
        assert body["success"] is False
        assert body["code"] == "no-model"

    def test_empty_goal(self, client):
        r = client.post("/api/v1/ai/generate-plan", json={"goal": "  "})
        assert r.json()["code"] == "empty"

    def test_llm_success(self, client, monkeypatch):
        async def fake_chat(goal, model, url, timeout_s=300.0):
            assert "shed" in goal
            return '{"entities": [{"type": "rect", "x1": 0, "y1": 0, "x2": 3000, "y2": 2000}], "layers": []}'

        monkeypatch.setattr(plan_llm, "chat_generate", fake_chat)
        monkeypatch.setattr(srv, "_llm_settings", {"ollama_url": "http://127.0.0.1:11434", "model": "test:model"})
        r = client.post("/api/v1/ai/generate-plan", json={"goal": "tiny shed"})
        body = r.json()
        assert body["success"] is True
        assert body["source"] == "llm"
        assert body["model"] == "test:model"
        assert len(body["entities"]) == 1

    def test_llm_garbage_fails(self, client, monkeypatch):
        async def fake_chat(goal, model, url, timeout_s=300.0):
            return "sorry, I cannot do that"

        monkeypatch.setattr(plan_llm, "chat_generate", fake_chat)
        monkeypatch.setattr(srv, "_llm_settings", {"ollama_url": "http://127.0.0.1:11434", "model": "test:model"})
        r = client.post("/api/v1/ai/generate-plan", json={"goal": "tiny shed"})
        body = r.json()
        assert body["success"] is False
        assert body["code"] == "json"

    def test_settings_persist_to_file(self, client, monkeypatch, tmp_path):
        async def fake_switch(keep, base_url=""):
            return {"evicted": [], "warmed": False, "engine": True}

        monkeypatch.setattr("qcad_mcp.services.llm_engine.switch_ollama_model", fake_switch)
        monkeypatch.setattr(srv, "_SETTINGS_FILE", str(tmp_path / "settings.json"))
        saved_model = srv._llm_settings.get("model", "")
        try:
            r = client.put("/api/v1/settings", json={"model": "persist:test"})
            assert r.status_code == 200
            import json as _json

            saved = _json.loads((tmp_path / "settings.json").read_text())
            assert saved["model"] == "persist:test"
        finally:
            srv._llm_settings["model"] = saved_model


_GOOD_JSON = (
    '{"entities": ['
    '{"type": "rect", "x1": 0, "y1": 0, "x2": 3000, "y2": 2000, "layer": "Walls"},'
    '{"type": "door", "x": 1350, "y": 0, "w": 900, "angle": 0, "layer": "Doors"}'
    "]}"
)


class FakeCtx:
    def __init__(self, text="", fail=False):
        self.text = text
        self.fail = fail
        self.calls = 0

    async def sample_step(self, **kwargs):
        self.calls += 1
        if self.fail:
            raise RuntimeError("no sampling host")
        return self.text


class TestSamplingText:
    def test_str(self):
        assert agentic_tools._sampling_text("hi") == "hi"

    def test_none(self):
        assert agentic_tools._sampling_text(None) == ""

    def test_text_attr(self):
        class R:
            text = "hello"

        assert agentic_tools._sampling_text(R()) == "hello"

    def test_content_blocks(self):
        class B:
            def __init__(self, text):
                self.text = text

        class R:
            content = [B("a"), B("b")]

        assert agentic_tools._sampling_text(R()) == "ab"


class TestPlanGenerate:
    async def test_sampling_path_spec_only(self):
        out = await agentic_tools.plan_generate(goal="tiny shed", create_dxf=False, ctx=FakeCtx(_GOOD_JSON))
        assert out["success"] is True
        assert out["source"] == "sampling"
        assert out["data"]["entity_count"] == 2

    async def test_sampling_failure_falls_back_to_ollama(self, monkeypatch):
        async def fake_chat(goal, model, url, timeout_s=300.0):
            return _GOOD_JSON

        monkeypatch.setattr(plan_llm, "chat_generate", fake_chat)
        monkeypatch.setattr(plan_llm, "load_server_llm_settings", lambda: ("m:test", "http://x:11434"))
        out = await agentic_tools.plan_generate(goal="tiny shed", create_dxf=False, ctx=FakeCtx(fail=True))
        assert out["success"] is True
        assert out["source"] == "ollama"
        assert out["model"] == "m:test"

    async def test_no_sampling_no_model_refuses(self, monkeypatch):
        monkeypatch.setattr(plan_llm, "load_server_llm_settings", lambda: ("", "http://x:11434"))
        out = await agentic_tools.plan_generate(goal="tiny shed", create_dxf=False, ctx=None)
        assert out["success"] is False
        assert out["code"] == "no-model"

    async def test_create_dxf_end_to_end(self):
        out = await agentic_tools.plan_generate(
            goal="tiny shed", filename="gen_test_shed", create_dxf=True, ctx=FakeCtx(_GOOD_JSON)
        )
        assert out["success"] is True
        assert out["output"] == "gen_test_shed.dxf"
        assert os.path.isfile(os.path.join(os.environ["QCAD_MCP_DEPOT"], "gen_test_shed.dxf"))

    async def test_empty_goal(self):
        out = await agentic_tools.plan_generate(goal="  ", ctx=FakeCtx(_GOOD_JSON))
        assert out["success"] is False
