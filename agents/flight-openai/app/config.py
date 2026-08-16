from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    service_name: str = os.getenv("SERVICE_NAME", "flight-agent")
    port: int = int(os.getenv("PORT", "8002"))
    public_url: str = os.getenv("PUBLIC_URL", "http://localhost:8002")
    # Default matches docker-compose.yml's MCP_FLIGHT_URL override (which
    # includes the /mcp path the Streamable HTTP server actually serves
    # on) — without it here, running this agent outside compose (e.g. a
    # bare `uvicorn` for local dev) silently pointed at the wrong path.
    mcp_flight_url: str = os.getenv("MCP_FLIGHT_URL", "http://mcp-flight:9001/mcp")
    request_timeout_seconds: float = float(os.getenv("AGENT_REQUEST_TIMEOUT_SECONDS", "30"))
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    # Fase 9 (§7/§56 "M6 Security"): see app/auth.py for what each
    # mode does. "dev" (spec default) requires DEV_AGENT_TOKEN on every
    # /a2a call; "jwt" requires a valid HS256 JWT instead.
    auth_mode: str = os.getenv("AUTH_MODE", "dev")
    dev_agent_token: str = os.getenv("DEV_AGENT_TOKEN", "local-development-only")
    jwt_secret: str = os.getenv("JWT_SECRET", "local-development-only-change-me")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()
