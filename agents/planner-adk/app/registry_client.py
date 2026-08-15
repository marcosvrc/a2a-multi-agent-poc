"""Client for the agent-registry service.

The Planner MUST discover specialists dynamically through the Registry +
Agent Card (PROJECT_SPEC.md §9: "Não fazer hard-code de capabilities no
Planner."). This module only fetches the directory; capability details
(skills) come from each agent's own Agent Card via the A2A client.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class RegistryClient:
    def __init__(self, base_url: str, timeout_seconds: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    async def list_agents(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(f"{self._base_url}/agents")
            resp.raise_for_status()
            return resp.json()

    async def get_agent(self, agent_id: str) -> dict[str, Any] | None:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(f"{self._base_url}/agents/{agent_id}")
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
