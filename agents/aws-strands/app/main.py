from __future__ import annotations

import logging
from functools import partial

from fastapi import FastAPI

from .a2a.agent_card import build_agent_card
from .a2a.server import InMemoryTaskStore, build_agent_card_router, build_jsonrpc_router
from .agent import handle_message
from .auth import verify_request
from .config import settings
from .telemetry import setup_logging, setup_tracing

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.service_name, version="0.1.0")

card = build_agent_card(settings.public_url)
task_store = InMemoryTaskStore()

# Fase 9 (§7/§56): gate the /a2a route the same way every other
# agent's is — see app/auth.py for what each AUTH_MODE does.
_require_auth = partial(
    verify_request, auth_mode=settings.auth_mode, dev_token=settings.dev_agent_token, jwt_secret=settings.jwt_secret
)

app.include_router(build_agent_card_router(card))
app.include_router(build_jsonrpc_router(handle_message, task_store, require_auth=_require_auth))

try:
    setup_tracing(app)
except Exception:  # noqa: BLE001
    logger.warning("tracing setup failed; continuing without OpenTelemetry")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "UP"}


@app.get("/ready")
async def ready() -> dict[str, object]:
    return {
        "status": "READY",
        "dependencies": {"mcp_weather": settings.mcp_weather_url, "model_provider": settings.model_provider or "mock"},
    }
