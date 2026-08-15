from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app import agent as agent_module
from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "UP"}


def test_agent_card_has_plan_trip_skill():
    card = client.get("/.well-known/agent-card.json").json()
    assert card["name"] == "planner-agent"
    assert any(s["id"] == "plan_trip" for s in card["skills"])


def test_foundation_check_completed_when_all_agents_reachable(monkeypatch):
    agents = [{"id": "mock-specialist-agent", "url": "http://mock:8099"}]
    monkeypatch.setattr(agent_module.registry_client, "list_agents", AsyncMock(return_value=agents))
    monkeypatch.setattr(
        agent_module.a2a_client,
        "send_text",
        AsyncMock(return_value={"status": {"state": "completed"}}),
    )

    resp = client.get("/v1/foundation-check")
    body = resp.json()
    assert body["status"] == "COMPLETED"
    assert body["discovered_agents"] == ["mock-specialist-agent"]


def test_foundation_check_partial_when_registry_empty(monkeypatch):
    monkeypatch.setattr(agent_module.registry_client, "list_agents", AsyncMock(return_value=[]))

    resp = client.get("/v1/foundation-check")
    body = resp.json()
    assert body["status"] == "PARTIAL"
    assert body["discovered_agents"] == []


def test_travel_request_returns_partial_with_documented_degradation(monkeypatch):
    monkeypatch.setattr(agent_module.registry_client, "list_agents", AsyncMock(return_value=[]))

    payload = {
        "origin": "Sao Paulo",
        "destination": "Florianopolis",
        "start_date": "2026-09-20",
        "end_date": "2026-09-24",
        "travelers": 2,
        "budget": 8000,
        "currency": "BRL",
        "preferences": ["beach"],
    }
    resp = client.post("/v1/travel-requests", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "PARTIAL"
    assert body["flight"]["status"] == "UNAVAILABLE"
    assert body["budget"]["budget_status"] == "UNKNOWN"
    assert body["enrichment"]["status"] == "SKIPPED"
    assert body["metadata"]["trace_id"]


def test_travel_request_rejects_invalid_date_range():
    payload = {
        "origin": "Sao Paulo",
        "destination": "Florianopolis",
        "start_date": "2026-09-24",
        "end_date": "2026-09-20",
        "travelers": 2,
        "budget": 8000,
        "currency": "BRL",
    }
    resp = client.post("/v1/travel-requests", json=payload)
    assert resp.status_code == 400
