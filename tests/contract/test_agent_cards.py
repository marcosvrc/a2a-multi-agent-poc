"""Contract tests: every Agent Card served by the M1 agents must contain
the mandatory fields required by PROJECT_SPEC.md §8, and at least one skill.

Run with the target agent already running locally, e.g.:

    AGENT_URLS="http://localhost:8001,http://localhost:8099" pytest tests/contract/test_agent_cards.py

If AGENT_URLS is not set, the test is skipped (it requires live services;
see tests/e2e for the docker-compose-driven variant).
"""
from __future__ import annotations

import os

import httpx
import pytest

REQUIRED_FIELDS = {"name", "description", "version", "capabilities", "skills"}


def _agent_urls() -> list[str]:
    raw = os.getenv("AGENT_URLS", "")
    return [u.strip() for u in raw.split(",") if u.strip()]


@pytest.mark.skipif(not _agent_urls(), reason="AGENT_URLS not set; this is a live contract test")
@pytest.mark.parametrize("base_url", _agent_urls())
def test_agent_card_is_well_formed(base_url: str):
    resp = httpx.get(f"{base_url}/.well-known/agent-card.json", timeout=10)
    resp.raise_for_status()
    card = resp.json()

    missing = REQUIRED_FIELDS - card.keys()
    assert not missing, f"Agent Card at {base_url} missing fields: {missing}"
    assert len(card["skills"]) >= 1, f"Agent Card at {base_url} declares no skills"
    for skill in card["skills"]:
        assert {"id", "name", "description"} <= skill.keys()
