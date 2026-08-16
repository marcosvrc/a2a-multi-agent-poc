import asyncio
import dataclasses
import json
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app import agent as agent_module
from app.config import settings
from app.main import app

# Fase 9 (§7/§56): the /a2a route now requires a bearer token by
# default (AUTH_MODE=dev) — every test in this file authenticates as
# whatever holds the shared DEV_AGENT_TOKEN, same as any real caller
# would in the default deployment.
client = TestClient(app, headers={"Authorization": f"Bearer {settings.dev_agent_token}"})


def test_health():
    assert client.get("/health").json() == {"status": "UP"}


def test_agent_card_has_plan_activities_skill():
    card = client.get("/.well-known/agent-card.json").json()
    assert card["name"] == "activity-agent"
    assert any(s["id"] == "plan_activities" for s in card["skills"])


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


def test_message_send_returns_daily_itinerary(monkeypatch):
    mock_places = {
        "provider": "mock",
        "places": [
            {"id": "PL-0001", "name": "Praia Central", "category": "beach", "duration_minutes": 180},
            {"id": "PL-0002", "name": "Museu de Arte", "category": "museum", "duration_minutes": 120},
        ],
    }
    mock_weather = {"provider": "mock", "forecast": {"date": "2026-09-20", "condition": "Ensolarado", "temperature_c": 27.0}}

    monkeypatch.setattr(agent_module, "search_places", AsyncMock(return_value=mock_places))
    monkeypatch.setattr(agent_module, "get_weather", AsyncMock(return_value=mock_weather))

    result = _send(
        {
            "destination": "Florianopolis",
            "start_date": "2026-09-20",
            "end_date": "2026-09-21",
            "preferences": ["beach"],
        },
        "ctx-activity-1",
    )

    assert result["status"] == "SUCCESS"
    assert len(result["days"]) == 2
    assert result["days"][0]["date"] == "2026-09-20"
    assert result["days"][0]["weather"] == "Ensolarado, 27.0°C"
    assert len(result["days"][0]["items"]) == 2
    assert result["days"][0]["items"][0]["start_time"] != result["days"][0]["items"][1]["start_time"]


def test_places_unavailable_returns_unavailable_status(monkeypatch):
    async def raise_error(*args, **kwargs):
        raise agent_module.McpToolError("connection refused")

    monkeypatch.setattr(agent_module, "search_places", raise_error)

    result = _send(
        {"destination": "Florianopolis", "start_date": "2026-09-20", "end_date": "2026-09-21"},
        "ctx-activity-2",
    )
    assert result["status"] == "UNAVAILABLE"
    assert result["days"] == []


def test_weather_unavailable_still_returns_success(monkeypatch):
    mock_places = {
        "provider": "mock",
        "places": [{"id": "PL-0001", "name": "Praia Central", "category": "beach", "duration_minutes": 180}],
    }

    async def raise_error(*args, **kwargs):
        raise agent_module.McpToolError("weather provider timeout")

    monkeypatch.setattr(agent_module, "search_places", AsyncMock(return_value=mock_places))
    monkeypatch.setattr(agent_module, "get_weather", raise_error)

    result = _send(
        {"destination": "Florianopolis", "start_date": "2026-09-20", "end_date": "2026-09-20"},
        "ctx-activity-3",
    )
    assert result["status"] == "SUCCESS"
    assert result["days"][0]["weather"] is None
    # Only one place available -> both daily slots rotate back to it.
    assert len(result["days"][0]["items"]) == 2
    assert result["days"][0]["items"][0]["name"] == result["days"][0]["items"][1]["name"]


def test_missing_required_field_fails_task():
    body = {
        "jsonrpc": "2.0",
        "id": "4",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": json.dumps({"destination": "Florianopolis"})}],
                "context_id": "ctx-activity-4",
            }
        },
    }
    resp = client.post("/a2a", json=body)
    task = resp.json()["result"]
    assert task["status"]["state"] == "failed"


def test_beeai_chat_model_routes_to_the_beeai_path(monkeypatch):
    # Confirms build_activity_result's gate actually calls _build_via_beeai
    # when BEEAI_CHAT_MODEL is set, and that it forwards the parsed
    # request untouched — without depending on beeai-framework's own
    # Tool/ChatModel classes (heavy, optional extra; not installed in
    # this test environment, see ADR-011).
    monkeypatch.setattr(agent_module, "settings", dataclasses.replace(agent_module.settings, beeai_chat_model="ollama:llama3.1"))
    fake_result = {"status": "SUCCESS", "days": [], "notes": "from beeai stub"}
    called_with = {}

    async def fake_build_via_beeai(req):
        called_with["req"] = req
        return fake_result

    monkeypatch.setattr(agent_module, "_build_via_beeai", fake_build_via_beeai)

    req = {"destination": "Florianopolis", "start_date": "2026-09-20", "end_date": "2026-09-21"}
    result = asyncio.run(agent_module.build_activity_result(req))

    assert called_with["req"] == req
    assert result == fake_result


def test_beeai_path_falls_back_to_deterministic_on_failure(monkeypatch):
    # BEEAI_CHAT_MODEL makes build_activity_result try _build_via_beeai
    # first; since beeai-framework isn't installed in this test
    # environment (optional extra — see pyproject.toml and the
    # INSTALL_BEEAI Dockerfile build arg), the import itself fails, which
    # must be caught and silently fall back to the deterministic path
    # rather than breaking the Planner's flow (§5.4: never invent data,
    # never block on the optional path).
    monkeypatch.setattr(agent_module, "settings", dataclasses.replace(agent_module.settings, beeai_chat_model="ollama:llama3.1"))
    mock_places = {"places": [{"name": "Praia Central", "category": "beach", "duration_minutes": 120}]}
    mock_weather = {"provider": "mock", "forecast": {"date": "2026-09-20", "condition": "Ensolarado", "temperature_c": 27.0}}
    monkeypatch.setattr(agent_module, "search_places", AsyncMock(return_value=mock_places))
    monkeypatch.setattr(agent_module, "get_weather", AsyncMock(return_value=mock_weather))

    req = {"destination": "Florianopolis", "start_date": "2026-09-20", "end_date": "2026-09-20"}
    result = asyncio.run(agent_module.build_activity_result(req))
    assert result["status"] in ("SUCCESS", "PARTIAL")
