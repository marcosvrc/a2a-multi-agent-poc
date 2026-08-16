"""Service-to-service auth for the A2A endpoint (PROJECT_SPEC.md §7/§56
"M6 Security", Fase 9).

Three modes, selected by `AUTH_MODE`:

- `"dev"` (default): static shared-secret bearer token (`DEV_AGENT_TOKEN`)
  — the spec's "API Key entre serviços ou token estático em
  desenvolvimento" (§7). Every agent in the stack shares the same
  `DEV_AGENT_TOKEN` value (from `.env`), so this only proves "the caller
  holds *a* valid credential", not *which* agent is calling.
- `"jwt"`: HMAC-signed JWT (HS256, shared secret `JWT_SECRET`) carrying
  the caller's own agent id as the `sub` claim — the "JWT" + "agent
  identity" deliverables of §56 M6. This is a deliberately minimal
  stand-in for a real IdP-issued token: no JWKS, no key rotation, no
  external Authorization Server. See
  `docs/adr/ADR-015-security-jwt-agent-identity-oidc-spike.md` for why a
  full OAuth 2.1/OIDC integration is scoped as a "spike" (design +
  smallest working proof) rather than a production IdP in this POC.
- `"none"`: no auth check at all — only meant for tests/local debugging,
  never the default (`AUTH_MODE` defaults to `"dev"`, matching §22's
  `.env.example`).

Only the `/a2a` route is protected. `/health`, `/ready` and the Agent
Card (`/.well-known/agent-card.json`) stay open on purpose: Agent Card
discovery (§9) and health/readiness checks must work before a caller has
any token to present, and gating them would break the exact
"descoberta dinâmica, nunca hard-coded" flow every prior phase relies on.
"""
from __future__ import annotations

import logging
import time

import jwt
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


def _extract_bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization")
    if not header or not header.lower().startswith("bearer "):
        return None
    return header[len("bearer "):].strip()


def verify_request(request: Request, *, auth_mode: str, dev_token: str, jwt_secret: str) -> str | None:
    """Raises `HTTPException(401)` if the request isn't authorized (never
    retried by A2AClient's own retry logic, per Fase 8 — a 401 is a 4xx,
    the far end rejected this deliberately). Returns the caller's agent
    identity (JWT `sub`) when known — `"dev"`/`"none"` modes carry no
    per-caller identity, just "some holder of the shared secret" (or
    nobody, in `"none"` mode).
    """
    mode = (auth_mode or "dev").strip().lower()
    if mode == "none":
        return None

    token = _extract_bearer_token(request)
    if token is None:
        raise HTTPException(status_code=401, detail="missing Authorization: Bearer <token> header")

    if mode == "jwt":
        try:
            claims = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        except jwt.PyJWTError as exc:
            raise HTTPException(status_code=401, detail=f"invalid JWT: {exc}") from exc
        return claims.get("sub")

    # mode == "dev" (default): plain constant-time-ish comparison against
    # the shared static token. Not cryptographically constant-time (no
    # hmac.compare_digest) — acceptable for a dev-only shared secret that
    # is never meant to gate anything but local/CI traffic; a real
    # deployment should run in "jwt" mode instead.
    if token != dev_token:
        raise HTTPException(status_code=401, detail="invalid token")
    return None


def mint_outgoing_token(*, auth_mode: str, dev_token: str, jwt_secret: str, agent_id: str, ttl_seconds: int = 300) -> str:
    """Builds the value this agent should send as
    `Authorization: Bearer <...>` when calling another agent over A2A, as
    this agent's own identity. Mirrors `verify_request`'s mode handling.
    """
    mode = (auth_mode or "dev").strip().lower()
    if mode == "jwt":
        now = int(time.time())
        claims = {"sub": agent_id, "iat": now, "exp": now + ttl_seconds}
        return jwt.encode(claims, jwt_secret, algorithm="HS256")
    return dev_token
