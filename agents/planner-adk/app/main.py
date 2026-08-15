from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException

from .a2a.agent_card import build_agent_card
from .a2a.server import InMemoryTaskStore, build_agent_card_router, build_jsonrpc_router
from .agent import handle_a2a_message, handle_travel_request, run_foundation_check
from .config import settings
from .schemas import TravelRequest, TravelResponse
from .telemetry import setup_logging, setup_tracing

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.service_name, version="0.1.0")

card = build_agent_card(settings.public_url)
task_store = InMemoryTaskStore()

app.include_router(build_agent_card_router(card))
app.include_router(build_jsonrpc_router(handle_a2a_message, task_store))

try:
    setup_tracing(app)
except Exception:  # noqa: BLE001
    logger.warning("tracing setup failed; continuing without OpenTelemetry")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "UP"}


@app.get("/ready")
async def ready() -> dict[str, object]:
    return {"status": "READY", "dependencies": {"agent_registry": settings.agent_registry_url}}


@app.get("/v1/foundation-check")
async def foundation_check() -> dict[str, object]:
    """M1 acceptance endpoint: proves Registry discovery + A2A round-trip."""
    return await run_foundation_check()


@app.post("/v1/travel-requests", response_model=TravelResponse)
async def create_travel_request(payload: TravelRequest) -> TravelResponse:
    if payload.start_date >= payload.end_date:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")
    return await handle_travel_request(payload)
