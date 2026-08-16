"""E2E test for Fase 7 (PROJECT_SPEC.md §43 / §5.6): the AWS Enrichment
Agent (Strands / Python, agents/aws-strands) is a real, optional fifth
specialist. Unlike flight/hotel/activity/budget, the Planner only even
attempts to call it when AWS_AGENT_ENABLED=true — with the stack up via
`make aws-local`/`make aws-lite` (`docker compose --profile aws up`) and
that env var set on the planner-agent container.

This file is split in two parts:

- Tests gated on PLANNER_URL alone (default-profile behavior): confirm
  that enrichment.status = SKIPPED never blocks status = COMPLETED. These
  pass against ANY running stack, aws profile or not, since
  AWS_AGENT_ENABLED defaults to false.
- Tests additionally gated on AWS_E2E_ENABLED=true (opt-in, since they
  require the stack to have been started with the aws profile AND
  AWS_AGENT_ENABLED=true on the planner): confirm the real
  aws-enrichment-agent responds via A2A with enrichment.status = SUCCESS
  and real content (weather_summary/destination_tips).

    PLANNER_URL=http://localhost:8001 pytest tests/e2e/test_fase7_enrichment.py
    PLANNER_URL=http://localhost:8001 AWS_E2E_ENABLED=true \\
        pytest tests/e2e/test_fase7_enrichment.py
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
AWS_E2E_ENABLED = os.getenv("AWS_E2E_ENABLED", "").strip().lower() == "true"
REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_DIR = REPO_ROOT / "contracts" / "schemas"

pytestmark = pytest.mark.skipif(not PLANNER_URL, reason="PLANNER_URL not set; this is a live E2E test")

_PAYLOAD = {
    "origin": "Sao Paulo",
    "destination": "Florianopolis",
    "start_date": "2026-09-20",
    "end_date": "2026-09-24",
    "travelers": 2,
    "budget": 8000,
    "currency": "BRL",
    "preferences": ["beach"],
}


def _schema_registry() -> Registry:
    resources = [(f.name, Resource.from_contents(json.loads(f.read_text()))) for f in SCHEMAS_DIR.glob("*.json")]
    return Registry().with_resources(resources)


def test_enrichment_skipped_or_unavailable_never_blocks_completed():
    """Whatever AWS_AGENT_ENABLED is set to on the running stack,
    enrichment must never be the reason status != COMPLETED — it's
    excluded from that calculation on purpose (§5.6/§11).
    """
    resp = httpx.post(f"{PLANNER_URL}/v1/travel-requests", json=_PAYLOAD, timeout=30)
    resp.raise_for_status()
    body = resp.json()

    schema = json.loads((SCHEMAS_DIR / "travel-response.schema.json").read_text())
    jsonschema.Draft202012Validator(schema, registry=_schema_registry()).validate(body)

    assert body["enrichment"]["status"] in ("SKIPPED", "SUCCESS", "UNAVAILABLE")
    # The four core specialists are unaffected by enrichment either way.
    assert body["flight"]["status"] == "SUCCESS"
    assert body["hotel"]["status"] == "SUCCESS"
    assert body["activities"]["status"] == "SUCCESS"
    assert body["budget"]["status"] == "SUCCESS"
    assert body["status"] == "COMPLETED"


@pytest.mark.skipif(not AWS_E2E_ENABLED, reason="AWS_E2E_ENABLED not set; requires stack up with --profile aws and AWS_AGENT_ENABLED=true")
def test_foundation_check_includes_aws_enrichment_agent():
    resp = httpx.get(f"{PLANNER_URL}/v1/foundation-check", timeout=30)
    resp.raise_for_status()
    body = resp.json()
    assert "aws-enrichment-agent" in body["discovered_agents"]


@pytest.mark.skipif(not AWS_E2E_ENABLED, reason="AWS_E2E_ENABLED not set; requires stack up with --profile aws and AWS_AGENT_ENABLED=true")
def test_travel_request_has_real_enrichment_when_aws_agent_enabled():
    resp = httpx.post(f"{PLANNER_URL}/v1/travel-requests", json=_PAYLOAD, timeout=30)
    resp.raise_for_status()
    body = resp.json()

    schema = json.loads((SCHEMAS_DIR / "travel-response.schema.json").read_text())
    jsonschema.Draft202012Validator(schema, registry=_schema_registry()).validate(body)

    enrichment = body["enrichment"]
    # With the aws-enrichment-agent up and reachable, it should succeed
    # (deterministic path is free and never fails outright) rather than
    # UNAVAILABLE/SKIPPED.
    assert enrichment["status"] == "SUCCESS"
    assert enrichment["provider"]
    # start_date is set in the payload, so a weather summary should be
    # present (real mcp-weather call, §5.4/§31 — never fabricated).
    assert enrichment["weather_summary"]
    assert len(enrichment["destination_tips"]) > 0
    # Enrichment being real and SUCCESS still must not change the
    # overall status calculation (§5.6/§11).
    assert body["status"] == "COMPLETED"
