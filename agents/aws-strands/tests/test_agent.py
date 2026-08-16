import dataclasses
import json
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app import agent as agent_module
from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "UP"}


def test_agent_card_has_enrich_destination_skill():
    card = client.get("/.well-known/agent-card.json").json()
    assert card["name"] == "aws-enrichment-agent"
    assert any(s["id"] == "enrich_destination" for s in card["skills"])


def _send(payload: dict, context_id: str) -> dict:
    body = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": json.dumps(payload)}],
                "context_id": context_id,
            }
        },
    }
    resp = client.post("/a2a", json=body)
    task = resp.json()["result"]
    return json.loads(task["status"]["message"]["parts"][0]["text"])


def test_deterministic_enrichment_returns_weather_and_tips(monkeypatch):
    mock_weather = {"provider": "mock", "forecast": {"date": "2026-09-20", "condition": "Ensolarado", "temperature_c": 27.0}}
    monkeypatch.setattr(agent_module, "get_weather", AsyncMock(return_value=mock_weather))

    result = _send(
        {"destination": "Florianopolis", "start_date": "2026-09-20", "preferences": ["beach", "gastronomy"]},
        "ctx-enrich-1",
    )

    assert result["status"] == "SUCCESS"
    assert result["provider"] == "mock"
    assert result["weather_summary"] == "Ensolarado, 27.0°C"
    assert len(result["destination_tips"]) <= 3
    assert any("praia" in t.lower() for t in result["destination_tips"])
    assert any("restaurantes" in t.lower() for t in result["destination_tips"])


def test_weather_unavailable_still_returns_success_via_tips(monkeypatch):
    async def raise_error(*args, **kwargs):
        raise agent_module.McpToolError("weather provider timeout")

    monkeypatch.setattr(agent_module, "get_weather", raise_error)

    result = _send({"destination": "Florianopolis", "start_date": "2026-09-20"}, "ctx-enrich-2")
    assert result["status"] == "SUCCESS"
    assert result["weather_summary"] is None
    # No matching preferences given -> falls back to the generic tip.
    assert len(result["destination_tips"]) == 1
    assert "Florianopolis" in result["destination_tips"][0]


def test_no_start_date_skips_weather_but_still_returns_tips():
    result = _send({"destination": "Florianopolis", "preferences": ["adventure"]}, "ctx-enrich-3")
    assert result["status"] == "SUCCESS"
    assert result["weather_summary"] is None
    assert result["destination_tips"]


def test_unknown_preferences_fall_back_to_generic_tip():
    result = _send({"destination": "Florianopolis", "preferences": ["not-a-real-tag"]}, "ctx-enrich-4")
    assert result["status"] == "SUCCESS"
    assert len(result["destination_tips"]) == 1
    assert "Florianopolis" in result["destination_tips"][0]


def test_missing_destination_fails_task():
    body = {
        "jsonrpc": "2.0",
        "id": "5",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": json.dumps({"start_date": "2026-09-20"})}],
                "context_id": "ctx-enrich-5",
            }
        },
    }
    resp = client.post("/a2a", json=body)
    task = resp.json()["result"]
    assert task["status"]["state"] == "failed"


def test_non_dict_json_body_returns_jsonrpc_error_not_500():
    resp = client.post("/a2a", json=[1, 2, 3])
    assert resp.status_code == 200
    body = resp.json()
    assert body["error"]["code"] == -32600


def test_strands_path_falls_back_to_deterministic_on_failure(monkeypatch):
    # MODEL_PROVIDER=ollama makes build_enrichment_result try
    # _build_via_strands first; since `strands` isn't installed in this
    # test environment (it's an optional extra — see pyproject.toml), the
    # import itself fails, which must be caught and silently fall back to
    # the deterministic path rather than breaking the Planner's flow
    # (§5.6: this agent must never block).
    # `settings` is a frozen dataclass instance — replace the module-level
    # binding agent.py's functions actually read, not a field on it.
    monkeypatch.setattr(agent_module, "settings", dataclasses.replace(agent_module.settings, model_provider="ollama"))
    mock_weather = {"provider": "mock", "forecast": {"date": "2026-09-20", "condition": "Nublado", "temperature_c": 20.0}}
    monkeypatch.setattr(agent_module, "get_weather", AsyncMock(return_value=mock_weather))

    result = _send({"destination": "Florianopolis", "start_date": "2026-09-20"}, "ctx-enrich-6")
    assert result["status"] == "SUCCESS"
    assert result["provider"] == "mock"
    assert result["weather_summary"] == "Nublado, 20.0°C"
