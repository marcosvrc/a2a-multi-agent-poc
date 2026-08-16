import json
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app import agent as agent_module
from app.a2a.models import AgentCapabilities, AgentCard, AgentSkill
from app.main import app

client = TestClient(app)


def _card(name: str, url: str, skill_id: str) -> AgentCard:
    return AgentCard(
        name=name,
        description=f"test double for {name}",
        version="0.1.0",
        url=url,
        capabilities=AgentCapabilities(),
        skills=[AgentSkill(id=skill_id, name=skill_id, description=skill_id)],
    )


def _mock_agent_cards(monkeypatch, cards_by_url: dict[str, AgentCard]) -> None:
    """Discovery-by-skill (§9) fetches each agent's Agent Card, so any test
    exercising handle_travel_request/_agents_by_skill must mock
    get_agent_card, not just registry_client.list_agents/send_text.
    """

    async def fake_get_agent_card(url: str) -> AgentCard:
        try:
            return cards_by_url[url]
        except KeyError:
            raise agent_module.A2AClientError(f"no agent card fixture for {url}")

    monkeypatch.setattr(agent_module.a2a_client, "get_agent_card", fake_get_agent_card)


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


def test_travel_request_returns_failed_when_no_agents_registered(monkeypatch):
    # With the registry empty, no core specialist can possibly succeed —
    # PARTIAL (documented in §11 for individual specialist degradation)
    # would misleadingly suggest some real data came back. FAILED is the
    # honest status here.
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
    assert body["status"] == "FAILED"
    assert body["flight"]["status"] == "UNAVAILABLE"
    assert body["budget"]["budget_status"] == "UNKNOWN"
    assert body["enrichment"]["status"] == "SKIPPED"
    assert body["metadata"]["trace_id"]


def test_travel_request_returns_partial_when_some_specialists_succeed(monkeypatch):
    # A genuine mixed outcome (flight succeeds, hotel/activity/budget
    # don't advertise the needed skill) must still land on PARTIAL, not
    # FAILED — only an all-zero outcome should ever be FAILED.
    agents = [{"id": "flight-agent", "url": "http://flight:8002"}]
    monkeypatch.setattr(agent_module.registry_client, "list_agents", AsyncMock(return_value=agents))
    _mock_agent_cards(monkeypatch, {"http://flight:8002": _card("flight-agent", "http://flight:8002", "search_flights")})

    flight_result = {"status": "SUCCESS", "options": [{"id": "FL-1", "price": 1000}], "recommended_option_id": "FL-1", "notes": ""}
    monkeypatch.setattr(agent_module.a2a_client, "send_text", AsyncMock(return_value=_completed_task(flight_result)))

    payload = {
        "origin": "Sao Paulo",
        "destination": "Florianopolis",
        "start_date": "2026-09-20",
        "end_date": "2026-09-24",
        "travelers": 2,
        "budget": 8000,
        "currency": "BRL",
    }
    resp = client.post("/v1/travel-requests", json=payload)
    body = resp.json()
    assert body["status"] == "PARTIAL"
    assert body["flight"]["status"] == "SUCCESS"
    assert body["hotel"]["status"] == "UNAVAILABLE"


def _completed_task(result_dict: dict) -> dict:
    return {"status": {"state": "completed", "message": {"parts": [{"kind": "text", "text": json.dumps(result_dict)}]}}}


_FOUR_SPECIALIST_AGENTS = [
    {"id": "flight-agent", "url": "http://flight:8002"},
    {"id": "hotel-agent", "url": "http://hotel:8003"},
    {"id": "activity-agent", "url": "http://activity:8004"},
    {"id": "budget-agent", "url": "http://budget:8005"},
]
_FOUR_SPECIALIST_CARDS = {
    "http://flight:8002": _card("flight-agent", "http://flight:8002", "search_flights"),
    "http://hotel:8003": _card("hotel-agent", "http://hotel:8003", "search_hotels"),
    "http://activity:8004": _card("activity-agent", "http://activity:8004", "plan_activities"),
    "http://budget:8005": _card("budget-agent", "http://budget:8005", "calculate_budget"),
}


def test_travel_request_completed_when_all_four_specialists_succeed(monkeypatch):
    monkeypatch.setattr(agent_module.registry_client, "list_agents", AsyncMock(return_value=_FOUR_SPECIALIST_AGENTS))
    _mock_agent_cards(monkeypatch, _FOUR_SPECIALIST_CARDS)

    flight_result = {"status": "SUCCESS", "options": [{"id": "FL-1", "price": 1000}], "recommended_option_id": "FL-1", "notes": ""}
    hotel_result = {"status": "SUCCESS", "options": [{"id": "HT-1", "price_per_night": 300}], "notes": ""}
    activity_result = {"status": "SUCCESS", "days": [{"date": "2026-09-20", "weather": None, "items": [{"name": "Praia", "start_time": "09:00"}]}], "notes": ""}
    budget_result = {"status": "SUCCESS", "budget_status": "WITHIN_BUDGET", "total": 3000, "limit": 8000, "remaining": 5000, "notes": ""}

    sent_payloads: dict[str, dict] = {}

    async def fake_send_text(url, text, context_id=None):
        sent_payloads[url] = json.loads(text)
        if "flight" in url:
            return _completed_task(flight_result)
        if "hotel" in url:
            return _completed_task(hotel_result)
        if "activity" in url:
            return _completed_task(activity_result)
        if "budget" in url:
            return _completed_task(budget_result)
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(agent_module.a2a_client, "send_text", fake_send_text)

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
    body = resp.json()
    assert body["status"] == "COMPLETED"
    assert body["budget"]["budget_status"] == "WITHIN_BUDGET"

    # request_id propagation: the Planner-generated request_id (echoed in
    # the response) must be what's actually sent to every specialist, not
    # the raw (here: absent/null) request_id from the inbound payload.
    request_id = body["request_id"]
    assert sent_payloads["http://flight:8002"]["request_id"] == request_id
    assert sent_payloads["http://hotel:8003"]["request_id"] == request_id
    assert sent_payloads["http://activity:8004"]["request_id"] == request_id
    assert sent_payloads["http://budget:8005"]["request_id"] == request_id


def test_specialist_task_state_failed_is_treated_as_unavailable(monkeypatch):
    # Previously, _parse_specialist_result ignored task["status"]["state"]
    # entirely and tried to parse the failure message as if it were a
    # real FlightResult — this asserts a `state: "failed"` task degrades
    # cleanly instead.
    agents = [{"id": "flight-agent", "url": "http://flight:8002"}]
    monkeypatch.setattr(agent_module.registry_client, "list_agents", AsyncMock(return_value=agents))
    _mock_agent_cards(monkeypatch, {"http://flight:8002": _card("flight-agent", "http://flight:8002", "search_flights")})

    failed_task = {
        "status": {
            "state": "failed",
            "message": {"parts": [{"kind": "text", "text": "invalid request: missing origin"}]},
        }
    }
    monkeypatch.setattr(agent_module.a2a_client, "send_text", AsyncMock(return_value=failed_task))

    payload = {
        "origin": "Sao Paulo",
        "destination": "Florianopolis",
        "start_date": "2026-09-20",
        "end_date": "2026-09-24",
        "travelers": 2,
        "budget": 8000,
        "currency": "BRL",
    }
    resp = client.post("/v1/travel-requests", json=payload)
    body = resp.json()
    assert body["flight"]["status"] == "UNAVAILABLE"
    assert "failed" in body["flight"]["notes"]
    assert "missing origin" in body["flight"]["notes"]


def test_specialist_task_state_working_is_treated_as_unavailable(monkeypatch):
    # A non-terminal state (the specialist hadn't finished) must not be
    # mis-parsed as if the attached message were the final result.
    agents = [{"id": "flight-agent", "url": "http://flight:8002"}]
    monkeypatch.setattr(agent_module.registry_client, "list_agents", AsyncMock(return_value=agents))
    _mock_agent_cards(monkeypatch, {"http://flight:8002": _card("flight-agent", "http://flight:8002", "search_flights")})

    working_task = {"status": {"state": "working"}}
    monkeypatch.setattr(agent_module.a2a_client, "send_text", AsyncMock(return_value=working_task))

    payload = {
        "origin": "Sao Paulo",
        "destination": "Florianopolis",
        "start_date": "2026-09-20",
        "end_date": "2026-09-24",
        "travelers": 2,
        "budget": 8000,
        "currency": "BRL",
    }
    resp = client.post("/v1/travel-requests", json=payload)
    body = resp.json()
    assert body["flight"]["status"] == "UNAVAILABLE"
    assert "not completed" in body["flight"]["notes"]


def test_agent_with_no_matching_skill_is_not_delegated_to(monkeypatch):
    # An agent registered but not advertising any of the skills the
    # Planner looks for (e.g. mock-specialist-agent's echo_ping) must
    # simply be skipped for travel-request delegation, not crash or be
    # treated as a flight/hotel/activity/budget specialist by virtue of
    # its agent-id string.
    agents = [{"id": "mock-specialist-agent", "url": "http://mock:8099"}]
    monkeypatch.setattr(agent_module.registry_client, "list_agents", AsyncMock(return_value=agents))
    _mock_agent_cards(monkeypatch, {"http://mock:8099": _card("mock-specialist-agent", "http://mock:8099", "echo_ping")})

    send_text = AsyncMock()
    monkeypatch.setattr(agent_module.a2a_client, "send_text", send_text)

    payload = {
        "origin": "Sao Paulo",
        "destination": "Florianopolis",
        "start_date": "2026-09-20",
        "end_date": "2026-09-24",
        "travelers": 2,
        "budget": 8000,
        "currency": "BRL",
    }
    resp = client.post("/v1/travel-requests", json=payload)
    body = resp.json()
    assert body["status"] == "FAILED"
    send_text.assert_not_called()


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
