"""Integration test proving the /a2a route is actually gated by
app.main's wiring (Fase 9, §7/§56) — not just that app.auth.verify_request
works in isolation (that's test_auth.py). Uses the real FastAPI app with
its real (default) settings: AUTH_MODE=dev, DEV_AGENT_TOKEN=
"local-development-only" — nothing in tests/conftest.py overrides these,
matching what a freshly-cloned repo's .env.example would give you.
"""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)

_ECHO_BODY = {
    "jsonrpc": "2.0",
    "id": "1",
    "method": "message/send",
    "params": {
        "message": {
            "role": "user",
            "parts": [{"kind": "text", "text": json.dumps({"origin": "GRU", "destination": "FLN", "start_date": "2026-01-01", "end_date": "2026-01-02", "travelers": 1, "budget": 1000, "currency": "BRL"})}],
            "context_id": "test-ctx",
        }
    },
}


def test_default_settings_are_auth_mode_dev():
    # Sanity check the premise of every other test in this file: nothing
    # in the test environment overrode AUTH_MODE/DEV_AGENT_TOKEN away
    # from what .env.example ships.
    assert settings.auth_mode == "dev"
    assert settings.dev_agent_token == "local-development-only"


def test_a2a_route_rejects_request_with_no_authorization_header():
    resp = client.post("/a2a", json=_ECHO_BODY)
    assert resp.status_code == 401


def test_a2a_route_rejects_request_with_wrong_token():
    resp = client.post("/a2a", json=_ECHO_BODY, headers={"Authorization": "Bearer wrong-token"})
    assert resp.status_code == 401


def test_a2a_route_accepts_request_with_correct_dev_token():
    resp = client.post("/a2a", json=_ECHO_BODY, headers={"Authorization": f"Bearer {settings.dev_agent_token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["jsonrpc"] == "2.0"
    assert "result" in body


def test_health_ready_and_agent_card_stay_open_without_any_auth_header():
    # §9: discovery and health checks must work before a caller has any
    # token to present.
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 200
    assert client.get("/.well-known/agent-card.json").status_code == 200
