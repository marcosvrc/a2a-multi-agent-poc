"""Minimal A2A client used by the Planner (and any agent) to call remote
agents over JSON-RPC 2.0, matching the server adapter in `server.py`.

Fase 8 (§27/§35 "Resiliência"): POSTs to `/a2a` retry on *transient
transport* failures — timeout, connection refused/reset, or a 5xx HTTP
status — with exponential backoff, up to `retry_attempts` extra tries.
A 4xx HTTP status is never retried (the far end rejected the request on
its own terms; retrying won't change that). A JSON-RPC-level error
(`error` field set on an otherwise-200 response) is likewise never
retried here — the specialist *did* receive and process the request, so
blindly repeating it would violate §27's "não repetir chamadas não
idempotentes sem controle"; that failure is surfaced as
`A2AClientError` and it's up to the caller (the Planner's circuit
breaker, `app/resilience.py`) to decide what happens to that agent next.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

import httpx

from .models import AgentCard, Message, TextPart

logger = logging.getLogger(__name__)

# Errors with no evidence the request was ever received/processed by the
# far end — safe to retry. httpx.HTTPStatusError is handled separately
# below since only its 5xx subset is transient.
_TRANSIENT_TRANSPORT_EXCEPTIONS = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.ReadError,
    httpx.RemoteProtocolError,
)


class A2AClientError(Exception):
    pass


class A2AClient:
    def __init__(
        self,
        timeout_seconds: float = 30.0,
        retry_attempts: int = 0,
        retry_backoff_base_seconds: float = 0.5,
    ) -> None:
        self._timeout = timeout_seconds
        self._retry_attempts = max(retry_attempts, 0)
        self._retry_backoff_base_seconds = retry_backoff_base_seconds

    async def _request_with_retry(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(self._retry_attempts + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.request(method, url, **kwargs)
                    resp.raise_for_status()
                    return resp
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code < 500:
                    raise  # 4xx: the far end rejected this on purpose, not transient.
                last_exc = exc
            except _TRANSIENT_TRANSPORT_EXCEPTIONS as exc:
                last_exc = exc

            if attempt >= self._retry_attempts:
                break
            delay = self._retry_backoff_base_seconds * (2**attempt)
            logger.warning(
                "A2A %s %s failed (attempt %d/%d): %s — retrying in %.2fs",
                method,
                url,
                attempt + 1,
                self._retry_attempts + 1,
                last_exc,
                delay,
            )
            await asyncio.sleep(delay)

        assert last_exc is not None
        raise last_exc

    async def get_agent_card(self, base_url: str) -> AgentCard:
        url = f"{base_url.rstrip('/')}/.well-known/agent-card.json"
        resp = await self._request_with_retry("GET", url)
        return AgentCard.model_validate(resp.json())

    async def send_text(
        self,
        base_url: str,
        text: str,
        *,
        context_id: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        message = Message(role="user", parts=[TextPart(text=text)], context_id=context_id)
        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "message/send",
            "params": {"message": message.model_dump(mode="json")},
        }
        url = f"{base_url.rstrip('/')}/a2a"
        resp = await self._request_with_retry("POST", url, json=payload, headers=headers or {})
        body = resp.json()
        if "error" in body and body["error"] is not None:
            raise A2AClientError(str(body["error"]))
        return body["result"]
