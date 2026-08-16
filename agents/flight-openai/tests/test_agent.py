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


def test_agent_card_has_search_flights_skill():
    card = client.get("/.well-known/agent-card.json").json()
    assert card["name"] == "flight-agent"
    assert any(s["id"] == "search_flights" for s in card["skills"])


def test_message_send_returns_ranked_flight_result(monkeypatch):
    mock_flights = {
        "provider": "mock",
        "flights": [
            {"id": "FL-002", "origin": "GRU", "destination": "FLN", "price": 900, "currency": "BRL", "provider": "mock"},
            {"id": "FL-001", "origin": "GRU", "destination": "FLN", "price": 700, "currency": "BRL", "provider": "mock"},
            {"id": "FL-003", "origin": "GRU", "destination": "FLN", "price": 1200, "currency": "BRL", "provider": "mock"},
        ],
    }
    monkeypatch.setattr(agent_module, "mcp_search_flights", AsyncMock(return_value=mock_flights))

    payload = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": json.dumps({
                    "origin": "GRU", "destination": "FLN",
                    "start_date": "2026-09-20", "end_date": "2026-09-24", "travelers": 2,
                })}],
                "context_id": "ctx-flight-1",
            }
        },
    }
    resp = client.post("/a2a", json=payload)
    body = resp.json()
    task = body["result"]
    assert task["status"]["state"] == "completed"

    result = json.loads(task["status"]["message"]["parts"][0]["text"])
    assert result["status"] == "SUCCESS"
    assert result["recommended_option_id"] == "FL-001"
    assert [o["id"] for o in result["options"]] == ["FL-001", "FL-002", "FL-003"]


def test_mcp_unavailable_returns_unavailable_status(monkeypatch):
    async def raise_error(*args, **kwargs):
        raise agent_module.McpFlightSearchError("connection refused")

    monkeypatch.setattr(agent_module, "mcp_search_flights", raise_error)

    payload = {
        "jsonrpc": "2.0",
        "id": "2",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": json.dumps({
                    "origin": "GRU", "destination": "FLN",
                    "start_date": "2026-09-20", "end_date": "2026-09-24", "travelers": 1,
                })}],
                "context_id": "ctx-flight-2",
            }
        },
    }
    resp = client.post("/a2a", json=payload)
    task = resp.json()["result"]
    result = json.loads(task["status"]["message"]["parts"][0]["text"])
    assert result["status"] == "UNAVAILABLE"


def test_missing_required_field_fails_task():
    payload = {
        "jsonrpc": "2.0",
        "id": "3",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": json.dumps({"origin": "GRU"})}],
                "context_id": "ctx-flight-3",
            }
        },
    }
    resp = client.post("/a2a", json=payload)
    task = resp.json()["result"]
    assert task["status"]["state"] == "failed"
