"""Minimal A2A client used by the Planner (and any agent) to call remote
agents over JSON-RPC 2.0, matching the server adapter in `server.py`.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

import httpx

from .models import AgentCard, Message, TextPart

logger = logging.getLogger(__name__)


class A2AClientError(Exception):
    pass


class A2AClient:
    def __init__(self, timeout_seconds: float = 30.0) -> None:
        self._timeout = timeout_seconds

    async def get_agent_card(self, base_url: str) -> AgentCard:
        url = f"{base_url.rstrip('/')}/.well-known/agent-card.json"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(url)
            resp.raise_for_status()
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
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, json=payload, headers=headers or {})
            resp.raise_for_status()
            body = resp.json()
            if "error" in body and body["error"] is not None:
                raise A2AClientError(str(body["error"]))
            return body["result"]
