from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    service_name: str = os.getenv("SERVICE_NAME", "activity-agent")
    port: int = int(os.getenv("PORT", "8004"))
    public_url: str = os.getenv("PUBLIC_URL", "http://localhost:8004")
    # Defaults match docker-compose.yml's overrides (which include the
    # /mcp path the Streamable HTTP servers actually serve on) — without
    # it here, running this agent outside compose silently pointed at the
    # wrong path.
    mcp_places_url: str = os.getenv("MCP_PLACES_URL", "http://mcp-places:9003/mcp")
    mcp_weather_url: str = os.getenv("MCP_WEATHER_URL", "http://mcp-weather:9004/mcp")
    request_timeout_seconds: float = float(os.getenv("AGENT_REQUEST_TIMEOUT_SECONDS", "30"))
    max_days: int = int(os.getenv("ACTIVITY_MAX_DAYS", "14"))
    # Optional: only used by the BeeAI-driven path (see app/agent.py and
    # docs/adr/ADR-011-activity-agent-beeai-optional.md). Any of the
    # backends BeeAI's ChatModel supports could be wired in here; this POC
    # only exercises the deterministic default path automatically.
    beeai_chat_model: str = os.getenv("BEEAI_CHAT_MODEL", "")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()
