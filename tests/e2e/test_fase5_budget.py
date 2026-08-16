"""E2E test for Fase 5 (PROJECT_SPEC.md §43): the real Budget Agent
(CrewAI / Python) answers over A2A — receiving the flight/hotel/activity
results the Planner already collected, not the raw request — and the
Planner returns a valid, schema-compliant BudgetResult inside the
TravelResponse. With all four core specialists real, the overall
TravelResponse status should now reach COMPLETED (not just PARTIAL).
Requires the stack running and PLANNER_URL set — same convention as
tests/e2e/test_fase2_flight.py, test_fase3_hotel.py, test_fase4_activity.py.

    PLANNER_URL=http://localhost:8001 pytest tests/e2e/test_fase5_budget.py
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


def test_foundation_check_includes_budget_agent():
    resp = httpx.get(f"{PLANNER_URL}/v1/foundation-check", timeout=30)
    resp.raise_for_status()
    body = resp.json()
    assert "budget-agent" in body["discovered_agents"]
    assert body["delegation_results"]["budget-agent"]["status"]["state"] == "completed"


def test_travel_request_completed_with_real_budget_within_limit():
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
    assert body["budget"]["status"] == "SUCCESS"
    assert body["budget"]["budget_status"] == "WITHIN_BUDGET"
    assert body["budget"]["total"] > 0
    assert body["budget"]["remaining"] == round(body["budget"]["limit"] - body["budget"]["total"], 2)
    # All four core specialists real and SUCCESS -> overall COMPLETED.
    assert body["status"] == "COMPLETED"


def test_travel_request_over_budget_when_limit_too_low():
    payload = {
        "origin": "Sao Paulo",
        "destination": "Florianopolis",
        "start_date": "2026-09-20",
        "end_date": "2026-09-24",
        "travelers": 2,
        "budget": 1,
        "currency": "BRL",
        "preferences": ["beach"],
    }
    resp = httpx.post(f"{PLANNER_URL}/v1/travel-requests", json=payload, timeout=30)
    resp.raise_for_status()
    body = resp.json()
    assert body["budget"]["budget_status"] == "OVER_BUDGET"
