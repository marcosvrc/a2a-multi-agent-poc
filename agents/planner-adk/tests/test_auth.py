"""Unit tests for app/auth.py (Fase 9, §7/§56 "M6 Security"): the three
AUTH_MODE behaviors (dev/jwt/none) in isolation, independent of any
FastAPI route wiring (that's covered separately in test_agent.py's
`test_a2a_endpoint_*` tests).
"""
from __future__ import annotations

import time

import jwt
import pytest
from fastapi import HTTPException, Request

from app.auth import mint_outgoing_token, verify_request


def _request_with_header(auth_header: str | None) -> Request:
    headers = [(b"authorization", auth_header.encode())] if auth_header else []
    scope = {"type": "http", "headers": headers, "method": "POST", "path": "/a2a"}
    return Request(scope)


# --- mode "none" -----------------------------------------------------------


def test_none_mode_allows_request_with_no_header():
    result = verify_request(
        _request_with_header(None), auth_mode="none", dev_token="secret", jwt_secret="jwtsecret"
    )
    assert result is None


def test_none_mode_ignores_a_bad_header_too():
    result = verify_request(
        _request_with_header("Bearer garbage"), auth_mode="none", dev_token="secret", jwt_secret="jwtsecret"
    )
    assert result is None


# --- mode "dev" (default) ---------------------------------------------------


def test_dev_mode_accepts_matching_token():
    result = verify_request(
        _request_with_header("Bearer secret"), auth_mode="dev", dev_token="secret", jwt_secret="jwtsecret"
    )
    assert result is None  # dev mode carries no per-caller identity


def test_dev_mode_rejects_missing_header():
    with pytest.raises(HTTPException) as exc_info:
        verify_request(_request_with_header(None), auth_mode="dev", dev_token="secret", jwt_secret="jwtsecret")
    assert exc_info.value.status_code == 401


def test_dev_mode_rejects_wrong_token():
    with pytest.raises(HTTPException) as exc_info:
        verify_request(
            _request_with_header("Bearer wrong-token"), auth_mode="dev", dev_token="secret", jwt_secret="jwtsecret"
        )
    assert exc_info.value.status_code == 401


def test_dev_mode_rejects_non_bearer_scheme():
    with pytest.raises(HTTPException):
        verify_request(
            _request_with_header("Basic secret"), auth_mode="dev", dev_token="secret", jwt_secret="jwtsecret"
        )


def test_dev_mode_is_the_default_when_auth_mode_is_empty_or_none_value():
    # settings.auth_mode defaults to "dev" in config.py; verify_request
    # itself also treats a falsy auth_mode the same way, so a
    # misconfigured/empty env var fails closed to "dev", not open.
    with pytest.raises(HTTPException):
        verify_request(_request_with_header(None), auth_mode="", dev_token="secret", jwt_secret="jwtsecret")


# --- mode "jwt" --------------------------------------------------------------


def test_jwt_mode_accepts_valid_token_and_returns_sub_claim():
    token = jwt.encode({"sub": "flight-agent", "iat": int(time.time())}, "jwtsecret", algorithm="HS256")
    result = verify_request(
        _request_with_header(f"Bearer {token}"), auth_mode="jwt", dev_token="secret", jwt_secret="jwtsecret"
    )
    assert result == "flight-agent"


def test_jwt_mode_rejects_token_signed_with_wrong_secret():
    token = jwt.encode({"sub": "flight-agent"}, "wrong-secret", algorithm="HS256")
    with pytest.raises(HTTPException) as exc_info:
        verify_request(
            _request_with_header(f"Bearer {token}"), auth_mode="jwt", dev_token="secret", jwt_secret="jwtsecret"
        )
    assert exc_info.value.status_code == 401


def test_jwt_mode_rejects_expired_token():
    now = int(time.time())
    token = jwt.encode({"sub": "flight-agent", "iat": now - 600, "exp": now - 300}, "jwtsecret", algorithm="HS256")
    with pytest.raises(HTTPException) as exc_info:
        verify_request(
            _request_with_header(f"Bearer {token}"), auth_mode="jwt", dev_token="secret", jwt_secret="jwtsecret"
        )
    assert exc_info.value.status_code == 401


def test_jwt_mode_rejects_a_dev_mode_static_token():
    # A plain static string is not a well-formed JWT — must fail closed,
    # not silently accept it as some degenerate "token".
    with pytest.raises(HTTPException):
        verify_request(
            _request_with_header("Bearer secret"), auth_mode="jwt", dev_token="secret", jwt_secret="jwtsecret"
        )


def test_jwt_mode_rejects_missing_header():
    with pytest.raises(HTTPException) as exc_info:
        verify_request(_request_with_header(None), auth_mode="jwt", dev_token="secret", jwt_secret="jwtsecret")
    assert exc_info.value.status_code == 401


# --- mint_outgoing_token -----------------------------------------------------


def test_mint_outgoing_token_dev_mode_returns_the_static_token():
    token = mint_outgoing_token(auth_mode="dev", dev_token="secret", jwt_secret="jwtsecret", agent_id="planner-agent")
    assert token == "secret"


def test_mint_outgoing_token_jwt_mode_returns_a_verifiable_jwt_with_own_identity():
    token = mint_outgoing_token(auth_mode="jwt", dev_token="secret", jwt_secret="jwtsecret", agent_id="planner-agent")
    claims = jwt.decode(token, "jwtsecret", algorithms=["HS256"])
    assert claims["sub"] == "planner-agent"
    assert "exp" in claims and "iat" in claims


def test_mint_then_verify_round_trip_in_jwt_mode():
    # The exact flow used in production: one agent mints its own token,
    # the callee verifies it and recovers the caller's identity.
    token = mint_outgoing_token(auth_mode="jwt", dev_token="secret", jwt_secret="jwtsecret", agent_id="budget-agent")
    caller_identity = verify_request(
        _request_with_header(f"Bearer {token}"), auth_mode="jwt", dev_token="secret", jwt_secret="jwtsecret"
    )
    assert caller_identity == "budget-agent"
