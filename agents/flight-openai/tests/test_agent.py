import asyncio
import dataclasses
import json
import sys
import types
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


def _install_fake_agents_sdk(monkeypatch, final_output_json: str) -> None:
    # Stubs the `agents` package (OpenAI Agents SDK) in sys.modules so the
    # LLM path in app/agent.py::_search_via_llm can run without the real,
    # heavy dependency installed — same technique used for `crewai` in
    # agents/budget-crewai/tests/test_agent.py and mirrors ADR-011's note
    # that these paths aren't exercised against a real backend in CI.
    fake_agents = types.ModuleType("agents")

    class FakeAgent:
        def __init__(self, **kwargs):
            pass

    class FakeRunResult:
        def __init__(self, final_output):
            self.final_output = final_output

    class FakeRunner:
        @staticmethod
        async def run(agent, _input):
            return FakeRunResult(final_output_json)

    def fake_function_tool(fn):
        return fn

    fake_agents.Agent = FakeAgent
    fake_agents.Runner = FakeRunner
    fake_agents.function_tool = fake_function_tool
    monkeypatch.setitem(sys.modules, "agents", fake_agents)


def test_llm_invalid_status_falls_back_to_deterministic(monkeypatch):
    # Regression test for the bug reported manually: the LLM path returned
    # status "OK" (not in the FlightResult enum), which used to sail
    # straight through to the Planner and fail there as a confusing
    # pydantic ValidationError instead of degrading gracefully like every
    # other specialist's optional LLM path.
    _install_fake_agents_sdk(monkeypatch, json.dumps({"status": "OK", "options": []}))
    monkeypatch.setattr(agent_module, "settings", dataclasses.replace(agent_module.settings, openai_api_key="sk-test"))

    mock_flights = {
        "provider": "mock",
        "flights": [{"id": "FL-001", "origin": "GRU", "destination": "FLN", "price": 700, "currency": "BRL", "provider": "mock"}],
    }
    monkeypatch.setattr(agent_module, "mcp_search_flights", AsyncMock(return_value=mock_flights))

    req = {"origin": "GRU", "destination": "FLN", "start_date": "2026-09-20", "end_date": "2026-09-24", "travelers": 1}
    result = asyncio.run(agent_module.build_flight_result(req))

    assert result["status"] == "SUCCESS"
    assert result["options"][0]["id"] == "FL-001"


def test_llm_valid_status_is_returned_as_is(monkeypatch):
    _install_fake_agents_sdk(monkeypatch, json.dumps({"status": "SUCCESS", "options": [{"id": "FL-LLM"}]}))
    monkeypatch.setattr(agent_module, "settings", dataclasses.replace(agent_module.settings, openai_api_key="sk-test"))

    req = {"origin": "GRU", "destination": "FLN", "start_date": "2026-09-20", "end_date": "2026-09-24", "travelers": 1}
    result = asyncio.run(agent_module.build_flight_result(req))

    assert result["status"] == "SUCCESS"
    assert result["options"][0]["id"] == "FL-LLM"
