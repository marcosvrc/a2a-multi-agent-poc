import asyncio
import dataclasses
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


def test_flight_hotel_activity_are_delegated_in_parallel(monkeypatch):
    # §43 Fase 6 "Paralelismo": Flight/Hotel/Activity delegation must
    # overlap, not run one after another. Each fake specialist call sleeps
    # 150ms; if they ran sequentially that's >=450ms total, but run
    # concurrently the whole fan-out should take close to one 150ms slot.
    import time as time_module

    monkeypatch.setattr(agent_module.registry_client, "list_agents", AsyncMock(return_value=_FOUR_SPECIALIST_AGENTS))
    _mock_agent_cards(monkeypatch, _FOUR_SPECIALIST_CARDS)

    flight_result = {"status": "SUCCESS", "options": [{"id": "FL-1", "price": 1000}], "recommended_option_id": "FL-1", "notes": ""}
    hotel_result = {"status": "SUCCESS", "options": [{"id": "HT-1", "price_per_night": 300}], "notes": ""}
    activity_result = {"status": "SUCCESS", "days": [], "notes": ""}
    budget_result = {"status": "SUCCESS", "budget_status": "WITHIN_BUDGET", "total": 3000, "limit": 8000, "remaining": 5000, "notes": ""}

    async def slow_send_text(url, text, context_id=None):
        if "budget" not in url:
            await asyncio.sleep(0.15)
        if "flight" in url:
            return _completed_task(flight_result)
        if "hotel" in url:
            return _completed_task(hotel_result)
        if "activity" in url:
            return _completed_task(activity_result)
        if "budget" in url:
            return _completed_task(budget_result)
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(agent_module.a2a_client, "send_text", slow_send_text)

    payload = {
        "origin": "Sao Paulo",
        "destination": "Florianopolis",
        "start_date": "2026-09-20",
        "end_date": "2026-09-24",
        "travelers": 2,
        "budget": 8000,
        "currency": "BRL",
    }
    started = time_module.perf_counter()
    resp = client.post("/v1/travel-requests", json=payload)
    elapsed = time_module.perf_counter() - started
    assert resp.json()["status"] == "COMPLETED"
    # Sequential would be >=0.45s (3 * 150ms) before even reaching Budget;
    # concurrent should land well under that.
    assert elapsed < 0.35, f"flight/hotel/activity delegation took {elapsed:.3f}s — looks sequential, not parallel"


def test_enrichment_skipped_when_aws_agent_disabled(monkeypatch):
    # §5.6/§11: AWS_AGENT_ENABLED=false (the default) means the Planner
    # doesn't even try to discover/call an enrichment skill — this must
    # never affect overall_status.
    monkeypatch.setattr(agent_module.registry_client, "list_agents", AsyncMock(return_value=_FOUR_SPECIALIST_AGENTS))
    _mock_agent_cards(monkeypatch, _FOUR_SPECIALIST_CARDS)

    flight_result = {"status": "SUCCESS", "options": [{"id": "FL-1", "price": 1000}], "recommended_option_id": "FL-1", "notes": ""}
    hotel_result = {"status": "SUCCESS", "options": [{"id": "HT-1", "price_per_night": 300}], "notes": ""}
    activity_result = {"status": "SUCCESS", "days": [], "notes": ""}
    budget_result = {"status": "SUCCESS", "budget_status": "WITHIN_BUDGET", "total": 3000, "limit": 8000, "remaining": 5000, "notes": ""}

    called_urls: list[str] = []

    async def fake_send_text(url, text, context_id=None):
        called_urls.append(url)
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
    }
    resp = client.post("/v1/travel-requests", json=payload)
    body = resp.json()
    assert body["status"] == "COMPLETED"
    assert body["enrichment"]["status"] == "SKIPPED"
    assert body["enrichment"]["provider"] is None
    for url in called_urls:
        assert "enrich" not in url, "enrichment agent must not be called when AWS_AGENT_ENABLED=false"


def test_enrichment_called_and_parsed_when_aws_agent_enabled(monkeypatch):
    monkeypatch.setattr(
        agent_module, "settings", dataclasses.replace(agent_module.settings, aws_agent_enabled=True)
    )
    agents = [*_FOUR_SPECIALIST_AGENTS, {"id": "aws-enrichment-agent", "url": "http://enrichment:8006"}]
    cards = {
        **_FOUR_SPECIALIST_CARDS,
        "http://enrichment:8006": _card("aws-enrichment-agent", "http://enrichment:8006", "enrich_destination"),
    }
    monkeypatch.setattr(agent_module.registry_client, "list_agents", AsyncMock(return_value=agents))
    _mock_agent_cards(monkeypatch, cards)

    flight_result = {"status": "SUCCESS", "options": [{"id": "FL-1", "price": 1000}], "recommended_option_id": "FL-1", "notes": ""}
    hotel_result = {"status": "SUCCESS", "options": [{"id": "HT-1", "price_per_night": 300}], "notes": ""}
    activity_result = {"status": "SUCCESS", "days": [], "notes": ""}
    budget_result = {"status": "SUCCESS", "budget_status": "WITHIN_BUDGET", "total": 3000, "limit": 8000, "remaining": 5000, "notes": ""}
    enrichment_result = {
        "status": "SUCCESS",
        "provider": "mock",
        "weather_summary": "Ensolarado, 27.0°C",
        "destination_tips": ["Leve protetor solar."],
    }

    async def fake_send_text(url, text, context_id=None):
        if "flight" in url:
            return _completed_task(flight_result)
        if "hotel" in url:
            return _completed_task(hotel_result)
        if "activity" in url:
            return _completed_task(activity_result)
        if "budget" in url:
            return _completed_task(budget_result)
        if "enrichment" in url:
            return _completed_task(enrichment_result)
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
    }
    resp = client.post("/v1/travel-requests", json=payload)
    body = resp.json()
    # A SUCCESS-but-optional enrichment must not change COMPLETED, and
    # its content must actually come through — this is the regression
    # test for the schema gap where EnrichmentResult had no
    # weather_summary/destination_tips fields and model_validate silently
    # dropped them.
    assert body["status"] == "COMPLETED"
    assert body["enrichment"]["status"] == "SUCCESS"
    assert body["enrichment"]["provider"] == "mock"
    assert body["enrichment"]["weather_summary"] == "Ensolarado, 27.0°C"
    assert body["enrichment"]["destination_tips"] == ["Leve protetor solar."]


def test_enrichment_unavailable_when_aws_enabled_but_no_agent_registered(monkeypatch):
    monkeypatch.setattr(
        agent_module, "settings", dataclasses.replace(agent_module.settings, aws_agent_enabled=True)
    )
    monkeypatch.setattr(agent_module.registry_client, "list_agents", AsyncMock(return_value=_FOUR_SPECIALIST_AGENTS))
    _mock_agent_cards(monkeypatch, _FOUR_SPECIALIST_CARDS)

    flight_result = {"status": "SUCCESS", "options": [{"id": "FL-1", "price": 1000}], "recommended_option_id": "FL-1", "notes": ""}
    hotel_result = {"status": "SUCCESS", "options": [{"id": "HT-1", "price_per_night": 300}], "notes": ""}
    activity_result = {"status": "SUCCESS", "days": [], "notes": ""}
    budget_result = {"status": "SUCCESS", "budget_status": "WITHIN_BUDGET", "total": 3000, "limit": 8000, "remaining": 5000, "notes": ""}

    async def fake_send_text(url, text, context_id=None):
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
    }
    resp = client.post("/v1/travel-requests", json=payload)
    body = resp.json()
    # No agent advertises enrich_destination -> UNAVAILABLE, but this
    # still must not drag overall_status down from COMPLETED (§11).
    assert body["status"] == "COMPLETED"
    assert body["enrichment"]["status"] == "UNAVAILABLE"


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


# ---------------------------------------------------------------------------
# Fase 8 (§27/§35 "Testes de resiliência"): CT-R01..CT-R06, plus the
# circuit breaker wiring itself. Retry-with-backoff's own control flow
# (attempt counts, 4xx vs 5xx, JSON-RPC errors never retried, exponential
# delay) is unit-tested in isolation in test_a2a_client.py; the tests
# below exercise it at the Planner level, in terms the spec actually
# states each CT-R0x by (overall status, per-specialist status).
# ---------------------------------------------------------------------------

_TRAVEL_PAYLOAD = {
    "origin": "Sao Paulo",
    "destination": "Florianopolis",
    "start_date": "2026-09-20",
    "end_date": "2026-09-24",
    "travelers": 2,
    "budget": 8000,
    "currency": "BRL",
    "preferences": ["beach"],
}


def test_ct_r01_flight_unavailable_yields_partial(monkeypatch):
    """CT-R01: Flight indisponível -> PARTIAL."""
    monkeypatch.setattr(agent_module.registry_client, "list_agents", AsyncMock(return_value=_FOUR_SPECIALIST_AGENTS))
    _mock_agent_cards(monkeypatch, _FOUR_SPECIALIST_CARDS)

    hotel_result = {"status": "SUCCESS", "options": [{"id": "HT-1", "price_per_night": 300}], "notes": ""}
    activity_result = {"status": "SUCCESS", "days": [], "notes": ""}
    budget_result = {"status": "SUCCESS", "budget_status": "WITHIN_BUDGET", "total": 3000, "limit": 8000, "remaining": 5000, "notes": ""}

    async def fake_send_text(url, text, context_id=None):
        if "flight" in url:
            raise agent_module.A2AClientError("flight-agent unreachable")
        if "hotel" in url:
            return _completed_task(hotel_result)
        if "activity" in url:
            return _completed_task(activity_result)
        if "budget" in url:
            return _completed_task(budget_result)
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(agent_module.a2a_client, "send_text", fake_send_text)

    resp = client.post("/v1/travel-requests", json=_TRAVEL_PAYLOAD)
    body = resp.json()
    assert body["status"] == "PARTIAL"
    assert body["flight"]["status"] == "UNAVAILABLE"
    assert body["hotel"]["status"] == "SUCCESS"


def test_ct_r02_hotel_persistent_timeout_yields_partial(monkeypatch):
    """CT-R02: Hotel retorna timeout -> retry; timeout; parcial.

    Exercises the real A2AClient (not a monkeypatched send_text) so the
    retry-with-backoff path in app/a2a/client.py actually runs: httpx
    itself is faked to raise httpx.TimeoutException on every hotel-agent
    call (and on every attempt, since the timeout is persistent — CT-R02
    describes a hotel-agent that never recovers within this request), and
    to succeed immediately for every other agent. Asserts both the
    retries actually happened (call count > 1) and the final outcome.
    """
    import httpx

    from tests.test_a2a_client import _FakeAsyncClient, _FakeResponse

    monkeypatch.setattr(
        agent_module, "settings", dataclasses.replace(agent_module.settings, max_retries=2, request_timeout_seconds=1)
    )
    # a2a_client was constructed at module import time with the *original*
    # settings; rebuild it so this test's lower retry_backoff actually
    # takes effect (keeps the test fast) without waiting out real
    # exponential delays.
    monkeypatch.setattr(
        agent_module,
        "a2a_client",
        agent_module.A2AClient(timeout_seconds=1, retry_attempts=2, retry_backoff_base_seconds=0.01),
    )
    monkeypatch.setattr(agent_module.registry_client, "list_agents", AsyncMock(return_value=_FOUR_SPECIALIST_AGENTS))

    flight_result = {"status": "SUCCESS", "options": [{"id": "FL-1", "price": 1000}], "recommended_option_id": "FL-1", "notes": ""}
    activity_result = {"status": "SUCCESS", "days": [], "notes": ""}
    budget_result = {"status": "SUCCESS", "budget_status": "WITHIN_BUDGET", "total": 3000, "limit": 8000, "remaining": 5000, "notes": ""}

    def _card_response(name: str, url: str, skill_id: str) -> "_FakeResponse":
        card = _card(name, url, skill_id).model_dump(mode="json")
        return _FakeResponse(200, card)

    def _result_response(result: dict) -> "_FakeResponse":
        return _FakeResponse(200, {"jsonrpc": "2.0", "id": "1", "result": _completed_task(result)})

    calls: list[tuple[str, str]] = []

    def _handler(method: str, url: str):
        if url.endswith("/.well-known/agent-card.json"):
            if "flight" in url:
                return _card_response("flight-agent", "http://flight:8002", "search_flights")
            if "hotel" in url:
                return _card_response("hotel-agent", "http://hotel:8003", "search_hotels")
            if "activity" in url:
                return _card_response("activity-agent", "http://activity:8004", "plan_activities")
            if "budget" in url:
                return _card_response("budget-agent", "http://budget:8005", "calculate_budget")
            raise AssertionError(f"unexpected agent card url: {url}")
        if "hotel" in url:
            return httpx.TimeoutException("hotel-agent timed out")
        if "flight" in url:
            return _result_response(flight_result)
        if "activity" in url:
            return _result_response(activity_result)
        if "budget" in url:
            return _result_response(budget_result)
        raise AssertionError(f"unexpected url: {url}")

    class _RoutingAsyncClient(_FakeAsyncClient):
        def __init__(self, **kwargs) -> None:
            super().__init__([], calls, **kwargs)

        async def request(self, method: str, url: str, **kwargs):
            calls.append((method, url))
            outcome = _handler(method, url)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

    monkeypatch.setattr("app.a2a.client.httpx.AsyncClient", lambda **kwargs: _RoutingAsyncClient(**kwargs))

    resp = client.post("/v1/travel-requests", json=_TRAVEL_PAYLOAD)
    body = resp.json()

    assert body["status"] == "PARTIAL"
    assert body["hotel"]["status"] == "UNAVAILABLE"
    assert body["flight"]["status"] == "SUCCESS"
    hotel_attempts = [c for c in calls if "hotel" in c[1] and c[1].endswith("/a2a")]
    assert len(hotel_attempts) == 3  # initial attempt + 2 retries, per max_retries=2


def test_ct_r04_aws_agent_disabled_yields_completed(monkeypatch):
    """CT-R04: AWS Agent desligado -> COMPLETED. Same scenario already
    covered by test_enrichment_skipped_when_aws_agent_disabled above;
    named here too so the CT-R0x -> test mapping from docs/testing.md is
    a straightforward 1:1 lookup.
    """
    monkeypatch.setattr(agent_module.registry_client, "list_agents", AsyncMock(return_value=_FOUR_SPECIALIST_AGENTS))
    _mock_agent_cards(monkeypatch, _FOUR_SPECIALIST_CARDS)

    flight_result = {"status": "SUCCESS", "options": [{"id": "FL-1", "price": 1000}], "recommended_option_id": "FL-1", "notes": ""}
    hotel_result = {"status": "SUCCESS", "options": [{"id": "HT-1", "price_per_night": 300}], "notes": ""}
    activity_result = {"status": "SUCCESS", "days": [], "notes": ""}
    budget_result = {"status": "SUCCESS", "budget_status": "WITHIN_BUDGET", "total": 3000, "limit": 8000, "remaining": 5000, "notes": ""}

    async def fake_send_text(url, text, context_id=None):
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

    resp = client.post("/v1/travel-requests", json=_TRAVEL_PAYLOAD)
    body = resp.json()
    assert body["status"] == "COMPLETED"
    assert body["enrichment"]["status"] == "SKIPPED"


def test_ct_r05_aws_agent_raises_error_yields_completed_with_enrichment_unavailable(monkeypatch):
    """CT-R05: AWS Agent lança erro -> COMPLETED, enrichment.status=UNAVAILABLE.

    Unlike test_enrichment_unavailable_when_aws_enabled_but_no_agent_registered
    (Fase 7 — the agent simply isn't registered), this simulates the agent
    being registered and discoverable but *erroring* when actually called.
    """
    monkeypatch.setattr(
        agent_module, "settings", dataclasses.replace(agent_module.settings, aws_agent_enabled=True)
    )
    agents = [*_FOUR_SPECIALIST_AGENTS, {"id": "aws-enrichment-agent", "url": "http://enrichment:8006"}]
    cards = {
        **_FOUR_SPECIALIST_CARDS,
        "http://enrichment:8006": _card("aws-enrichment-agent", "http://enrichment:8006", "enrich_destination"),
    }
    monkeypatch.setattr(agent_module.registry_client, "list_agents", AsyncMock(return_value=agents))
    _mock_agent_cards(monkeypatch, cards)

    flight_result = {"status": "SUCCESS", "options": [{"id": "FL-1", "price": 1000}], "recommended_option_id": "FL-1", "notes": ""}
    hotel_result = {"status": "SUCCESS", "options": [{"id": "HT-1", "price_per_night": 300}], "notes": ""}
    activity_result = {"status": "SUCCESS", "days": [], "notes": ""}
    budget_result = {"status": "SUCCESS", "budget_status": "WITHIN_BUDGET", "total": 3000, "limit": 8000, "remaining": 5000, "notes": ""}

    async def fake_send_text(url, text, context_id=None):
        if "flight" in url:
            return _completed_task(flight_result)
        if "hotel" in url:
            return _completed_task(hotel_result)
        if "activity" in url:
            return _completed_task(activity_result)
        if "budget" in url:
            return _completed_task(budget_result)
        if "enrichment" in url:
            raise agent_module.A2AClientError("aws-enrichment-agent crashed")
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(agent_module.a2a_client, "send_text", fake_send_text)

    resp = client.post("/v1/travel-requests", json=_TRAVEL_PAYLOAD)
    body = resp.json()
    assert body["status"] == "COMPLETED"
    assert body["enrichment"]["status"] == "UNAVAILABLE"


def test_ct_r06_budget_failure_yields_partial_with_budget_status_unknown(monkeypatch):
    """CT-R06: Budget falha -> PARTIAL, budget.status=UNKNOWN."""
    monkeypatch.setattr(agent_module.registry_client, "list_agents", AsyncMock(return_value=_FOUR_SPECIALIST_AGENTS))
    _mock_agent_cards(monkeypatch, _FOUR_SPECIALIST_CARDS)

    flight_result = {"status": "SUCCESS", "options": [{"id": "FL-1", "price": 1000}], "recommended_option_id": "FL-1", "notes": ""}
    hotel_result = {"status": "SUCCESS", "options": [{"id": "HT-1", "price_per_night": 300}], "notes": ""}
    activity_result = {"status": "SUCCESS", "days": [], "notes": ""}

    async def fake_send_text(url, text, context_id=None):
        if "flight" in url:
            return _completed_task(flight_result)
        if "hotel" in url:
            return _completed_task(hotel_result)
        if "activity" in url:
            return _completed_task(activity_result)
        if "budget" in url:
            raise agent_module.A2AClientError("budget-agent crashed")
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(agent_module.a2a_client, "send_text", fake_send_text)

    resp = client.post("/v1/travel-requests", json=_TRAVEL_PAYLOAD)
    body = resp.json()
    assert body["status"] == "PARTIAL"
    # The distinguishing assertion vs. CT-R01/CT-R05: Budget's own
    # "status" field (not just budget_status) is UNKNOWN, not UNAVAILABLE
    # — see _parse_specialist_result's unavailable_status param.
    assert body["budget"]["status"] == "UNKNOWN"
    assert body["budget"]["budget_status"] == "UNKNOWN"


def test_circuit_breaker_opens_after_threshold_and_skips_further_delegation(monkeypatch):
    """Fase 8 (§27/§35): after `circuit_breaker_failure_threshold`
    consecutive failed delegations to the same agent, further delegation
    attempts must be short-circuited (no send_text call at all) until the
    cooldown elapses — not just individually degrade to UNAVAILABLE every
    time, which would mean every subsequent request still pays for a full
    timeout against an agent already known to be down.
    """
    from app.resilience import CircuitBreakerRegistry

    agent_module.circuit_breakers = CircuitBreakerRegistry(failure_threshold=2, reset_timeout_seconds=30)

    call_count = 0

    async def failing_send_text(url, text, context_id=None):
        nonlocal call_count
        call_count += 1
        raise agent_module.A2AClientError("boom")

    monkeypatch.setattr(agent_module.a2a_client, "send_text", failing_send_text)

    agent = {"id": "flaky-agent", "url": "http://flaky:9999"}
    results = [asyncio.run(agent_module._delegate_to_agent(agent, "payload", "req-1")) for _ in range(4)]

    assert all(r is None for r in results)
    # Only the first 2 calls actually reached send_text (threshold=2);
    # the 3rd and 4th were short-circuited by the OPEN breaker.
    assert call_count == 2
    assert agent_module.circuit_breakers.get("flaky-agent").state.value == "OPEN"


def test_circuit_breaker_is_per_agent_not_global(monkeypatch):
    """A breaker OPENing for one agent must never affect delegation to a
    different agent — each agent id gets its own independent breaker.
    """
    from app.resilience import CircuitBreakerRegistry

    agent_module.circuit_breakers = CircuitBreakerRegistry(failure_threshold=1, reset_timeout_seconds=30)

    async def routed_send_text(url, text, context_id=None):
        if "flaky" in url:
            raise agent_module.A2AClientError("boom")
        return _completed_task({"status": "SUCCESS", "options": [], "notes": ""})

    monkeypatch.setattr(agent_module.a2a_client, "send_text", routed_send_text)

    flaky_agent = {"id": "flaky-agent", "url": "http://flaky:9999"}
    healthy_agent = {"id": "healthy-agent", "url": "http://healthy:9998"}

    assert asyncio.run(agent_module._delegate_to_agent(flaky_agent, "payload", "req-1")) is None
    assert agent_module.circuit_breakers.get("flaky-agent").state.value == "OPEN"

    healthy_result = asyncio.run(agent_module._delegate_to_agent(healthy_agent, "payload", "req-1"))
    assert healthy_result is not None
    assert agent_module.circuit_breakers.get("healthy-agent").state.value == "CLOSED"
