"""E2E test for Fase 6 (PROJECT_SPEC.md §43 "Paralelismo"): Flight, Hotel
and Activity are now delegated concurrently by the Planner
(`asyncio.gather` in `agents/planner-adk/app/agent.py`,
`handle_travel_request`) instead of one after another. Budget is
excluded from that fan-out on purpose (§5.5: it needs their *results*).

This is a correctness regression check, not a timing benchmark — the
mock specialists in this stack respond in well under 100ms each, so a
live wall-clock assertion here would be too noisy to be a reliable
signal either way. The real proof that the three calls actually overlap
lives in agents/planner-adk/tests/test_agent.py::
test_flight_hotel_activity_are_delegated_in_parallel, which controls
latency deterministically via a mocked, artificially slow send_text.
What this test verifies is that switching flight/hotel/activity
delegation from sequential to concurrent didn't change the outcome: the
same COMPLETED, schema-valid TravelResponse Fase 5's E2E test already
established.

Requires the stack running and PLANNER_URL set — same convention as
tests/e2e/test_fase2_flight.py .. test_fase5_budget.py.

    PLANNER_URL=http://localhost:8001 pytest tests/e2e/test_fase6_parallel.py
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import jsonschema
import pytest
from referencing import Registry, Resource

PLANNER_URL = os.getenv("PLANNER_URL")
REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_DIR = REPO_ROOT / "contracts" / "schemas"

pytestmark = pytest.mark.skipif(not PLANNER_URL, reason="PLANNER_URL not set; this is a live E2E test")


def _schema_registry() -> Registry:
    resources = [(f.name, Resource.from_contents(json.loads(f.read_text()))) for f in SCHEMAS_DIR.glob("*.json")]
    return Registry().with_resources(resources)


def test_travel_request_still_completed_after_parallel_delegation():
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
    resp = httpx.post(f"{PLANNER_URL}/v1/travel-requests", json=payload, timeout=30)
    resp.raise_for_status()
    body = resp.json()

    schema = json.loads((SCHEMAS_DIR / "travel-response.schema.json").read_text())
    jsonschema.Draft202012Validator(schema, registry=_schema_registry()).validate(body)

    assert body["status"] == "COMPLETED"
    assert body["flight"]["status"] == "SUCCESS"
    assert body["hotel"]["status"] == "SUCCESS"
    assert body["activities"]["status"] == "SUCCESS"
    assert body["budget"]["status"] == "SUCCESS"
    # request_id propagation (fixed in the Fase 5 review pass) must still
    # hold with concurrent delegation: every specialist call carries the
    # Planner-generated request_id, and the response echoes the same one.
    assert body["request_id"]
    assert body["metadata"]["correlation_id"] == body["request_id"]


def test_agent_with_no_matching_skill_does_not_break_parallel_fan_out():
    # mock-specialist-agent (skill echo_ping) is registered alongside the
    # four real specialists. It must simply be ignored by the
    # flight/hotel/activity fan-out (§9: selection is by skill, not by
    # "delegate to everyone registered") rather than raising inside
    # asyncio.gather and taking the other three down with it.
    resp = httpx.get(f"{PLANNER_URL}/v1/foundation-check", timeout=30)
    resp.raise_for_status()
    body = resp.json()
    assert "mock-specialist-agent" in body["discovered_agents"]

    payload = {
        "origin": "Sao Paulo",
        "destination": "Florianopolis",
        "start_date": "2026-09-20",
        "end_date": "2026-09-24",
        "travelers": 1,
        "budget": 8000,
        "currency": "BRL",
    }
    resp = httpx.post(f"{PLANNER_URL}/v1/travel-requests", json=payload, timeout=30)
    resp.raise_for_status()
    body = resp.json()
    assert body["status"] == "COMPLETED"
