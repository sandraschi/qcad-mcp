"""Endpoint tests for vends surfaces (Apps hub + LLM)."""

import pytest
from fastapi.testclient import TestClient

import qcad_mcp.server as srv


@pytest.fixture(scope="module")
def client():
    return TestClient(srv.app)


class TestAppsHub:
    def test_hub_lists(self, client):
        r = client.get("/api/apps")
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body.get("apps"), list)
        # Non-empty only where a fleet checkout exists (Goliath D:\Dev\repos);
        # CI runners check out this repo alone, so emptiness is valid there.
        assert "fleet_total" in body

    def test_health_closed_port_false(self, client):
        r = client.get("/api/apps/health", params={"port": 9})
        assert r.status_code == 200
        assert r.json().get("alive") is False

    def test_ensure_unknown_fails_safe(self, client):
        r = client.post("/api/apps/ensure", json={"id": "no-such-app-xyz", "port": 0})
        assert r.status_code == 200
        body = r.json()
        assert body.get("success") is False
        assert "error" in body


class TestLlm:
    def test_models_shape(self, client):
        r = client.get("/api/llm/models", params={"provider": "ollama"})
        assert r.status_code == 200
        body = r.json()
        assert body["provider"] == "ollama"
        assert isinstance(body["models"], list)
        assert body["source"] in ("live", "none")

    def test_models_non_ollama_none(self, client):
        r = client.get("/api/llm/models", params={"provider": "lmstudio"})
        assert r.status_code == 200
        assert r.json()["source"] == "none"

    def test_chat_empty_model_guarded(self, client):
        r = client.post("/api/llm/chat", json={"provider": "ollama", "model": "", "prompt": "hi"})
        assert r.status_code == 200
        assert "error" in r.json()

    def test_unload_engine_down_502(self, client, monkeypatch):
        async def fake_switch(keep, base_url=""):
            return {"evicted": [], "warmed": False, "engine": False}

        monkeypatch.setattr("qcad_mcp.services.llm_engine.switch_ollama_model", fake_switch)
        r = client.post("/api/llm/unload", json={"provider": "ollama", "endpoint": "http://127.0.0.1:9"})
        assert r.status_code == 502

    def test_loaded_shape(self, client):
        r = client.get("/api/llm/loaded", params={"provider": "ollama", "endpoint": "http://127.0.0.1:9"})
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert isinstance(body["models"], list)

    def test_gpus_shape(self, client):
        r = client.get("/api/llm/gpus")
        assert r.status_code == 200
        assert isinstance(r.json().get("gpus"), list)

    def test_settings_save_reports_switch(self, client, monkeypatch, tmp_path):
        async def fake_switch(keep, base_url=""):
            return {"evicted": ["old:1b"], "warmed": True, "engine": True}

        monkeypatch.setattr("qcad_mcp.services.llm_engine.switch_ollama_model", fake_switch)
        # Redirect persistence: settings PUTs must never clobber the real user file.
        monkeypatch.setattr(srv, "_SETTINGS_FILE", str(tmp_path / "settings.json"))
        saved_model = srv._llm_settings.get("model", "")
        try:
            r = client.put("/api/v1/settings", json={"model": "llama3.2:3b"})
            assert r.status_code == 200
            sw = r.json().get("llm_switch")
            assert sw and sw["warmed"] is True and sw["evicted"] == ["old:1b"]
        finally:
            srv._llm_settings["model"] = saved_model
