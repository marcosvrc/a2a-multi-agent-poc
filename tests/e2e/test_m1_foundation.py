"""E2E test for Milestone M1 (PROJECT_SPEC.md §51): Planner discovers the
Mock Specialist Agent via the Agent Registry and completes an A2A
round-trip. Requires the stack to be running (docker compose up, or the
services started manually) and PLANNER_URL pointing at the Planner.

    PLANNER_URL=http://localhost:8001 pytest tests/e2e/test_m1_foundation.py

Skipped automatically when PLANNER_URL is not set, so it does not break
`pytest -q` runs that only care about unit/contract tests.
"""
from __future__ import annotations

import os

import httpx
import pytest

PLANNER_URL = os.getenv("PLANNER_URL")

pytestmark = pytest.mark.skipif(not PLANNER_URL, reason="PLANNER_URL not set; this is a live E2E test")


def test_foundation_check_discovers_and_calls_mock_agent():
    resp = httpx.get(f"{PLANNER_URL}/v1/foundation-check", timeout=30)
    resp.raise_for_status()
    body = resp.json()

    assert body["status"] == "COMPLETED"
    assert "mock-specialist-agent" in body["discovered_agents"]
    result = body["delegation_results"]["mock-specialist-agent"]
    assert result["status"]["state"] == "completed"


def test_travel_request_end_to_end_returns_valid_travel_response():
    payload = {
        "origin": "Sao Paulo",
        "destination": "Florianopolis",
        "start_date": "2026-09-20",
        "end_date": "2026-09-24",
        "travelers": 2,
        "budget": 8000,
        "currency": "BRL",
        "preferences": ["beach", "gastronomy", "outdoor"],
    }
    resp = httpx.post(f"{PLANNER_URL}/v1/travel-requests", json=payload, timeout=30)
    resp.raise_for_status()
    body = resp.json()

    assert body["request_id"]
    assert body["status"] in {"COMPLETED", "PARTIAL", "FAILED"}
    assert body["metadata"]["trace_id"]
