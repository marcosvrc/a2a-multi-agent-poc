"""E2E test for Fase 2 (PROJECT_SPEC.md §43): the real Flight Agent
answers over A2A and the Planner returns a valid, schema-compliant
FlightResult inside the TravelResponse. Requires the stack running and
PLANNER_URL set — same convention as tests/e2e/test_m1_foundation.py.

    PLANNER_URL=http://localhost:8001 pytest tests/e2e/test_fase2_flight.py
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


def test_foundation_check_includes_flight_agent():
    resp = httpx.get(f"{PLANNER_URL}/v1/foundation-check", timeout=30)
    resp.raise_for_status()
    body = resp.json()
    assert "flight-agent" in body["discovered_agents"]
    assert body["delegation_results"]["flight-agent"]["status"]["state"] == "completed"


def test_travel_request_returns_real_flight_options():
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
    assert 1 <= len(body["flight"]["options"]) <= 5
    assert body["flight"]["recommended_option_id"]
    # Overall status depends on which other specialists are registered in
    # the running stack (this test only asserts flight-agent's own
    # contribution); see test_fase5_budget.py for the full COMPLETED case.
