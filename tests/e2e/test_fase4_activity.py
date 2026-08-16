"""E2E test for Fase 4 (PROJECT_SPEC.md §43): the real Activity Agent
(BeeAI Framework / Python) answers over A2A and the Planner returns a
valid, schema-compliant ActivityResult inside the TravelResponse.
Requires the stack running and PLANNER_URL set — same convention as
tests/e2e/test_fase2_flight.py and tests/e2e/test_fase3_hotel.py.

    PLANNER_URL=http://localhost:8001 pytest tests/e2e/test_fase4_activity.py
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


def test_foundation_check_includes_activity_agent():
    resp = httpx.get(f"{PLANNER_URL}/v1/foundation-check", timeout=30)
    resp.raise_for_status()
    body = resp.json()
    assert "activity-agent" in body["discovered_agents"]
    assert body["delegation_results"]["activity-agent"]["status"]["state"] == "completed"


def test_travel_request_returns_real_activity_itinerary():
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

    assert body["flight"]["status"] == "SUCCESS"
    assert body["hotel"]["status"] == "SUCCESS"
    assert body["activities"]["status"] == "SUCCESS"
    # 2026-09-20 through 2026-09-24 inclusive -> 5 days.
    assert len(body["activities"]["days"]) == 5
    for day in body["activities"]["days"]:
        assert day["items"]
        start_times = [item["start_time"] for item in day["items"]]
        assert len(start_times) == len(set(start_times))  # no scheduling conflicts
    # Overall status depends on whether budget-agent is registered in the
    # running stack; see test_fase5_budget.py for the full COMPLETED case.
