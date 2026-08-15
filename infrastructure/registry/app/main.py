"""Agent Registry — didactic service that lists known A2A agents.

This is NOT a replacement for the A2A Agent Card. It is a small directory
service the Planner uses to discover which agents exist, where they live,
and whether they are required for the main flow, so that capabilities are
never hard-coded into the Planner.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("agent-registry")

app = FastAPI(title="agent-registry", version="0.1.0")

REGISTRY_FILE = Path(os.getenv("REGISTRY_FILE", "/app/agents.json"))


def _load_agents() -> list[dict[str, Any]]:
    if not REGISTRY_FILE.exists():
        logger.warning("registry file %s not found, returning empty list", REGISTRY_FILE)
        return []
    with REGISTRY_FILE.open("r", encoding="utf-8") as fh:
        return json.load(fh)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "UP"}


@app.get("/ready")
async def ready() -> dict[str, Any]:
    agents = _load_agents()
    return {"status": "READY", "dependencies": {"registry_file": "UP" if agents is not None else "DOWN"}}


@app.get("/agents")
async def list_agents() -> list[dict[str, Any]]:
    return _load_agents()


@app.get("/agents/{agent_id}")
async def get_agent(agent_id: str) -> dict[str, Any]:
    for agent in _load_agents():
        if agent["id"] == agent_id:
            return agent
    raise HTTPException(status_code=404, detail=f"agent '{agent_id}' not found")


@app.get("/agents/{agent_id}/health")
async def get_agent_health(agent_id: str) -> JSONResponse:
    agent = None
    for candidate in _load_agents():
        if candidate["id"] == agent_id:
            agent = candidate
            break
    if agent is None:
        raise HTTPException(status_code=404, detail=f"agent '{agent_id}' not found")

    health_url = f"{agent['url'].rstrip('/')}/health"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(health_url)
            resp.raise_for_status()
            return JSONResponse(content=resp.json())
    except Exception as exc:  # noqa: BLE001 — registry must degrade gracefully
        logger.warning("health check failed for %s: %s", agent_id, exc)
        return JSONResponse(status_code=503, content={"status": "DOWN", "error": str(exc)})
