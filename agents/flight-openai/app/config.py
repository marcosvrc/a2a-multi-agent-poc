from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    service_name: str = os.getenv("SERVICE_NAME", "flight-agent")
    port: int = int(os.getenv("PORT", "8002"))
    public_url: str = os.getenv("PUBLIC_URL", "http://localhost:8002")
    mcp_flight_url: str = os.getenv("MCP_FLIGHT_URL", "http://mcp-flight:9001")
    request_timeout_seconds: float = float(os.getenv("AGENT_REQUEST_TIMEOUT_SECONDS", "30"))
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()
