from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    service_name: str = os.getenv("SERVICE_NAME", "planner-agent")
    port: int = int(os.getenv("PORT", "8001"))
    public_url: str = os.getenv("PUBLIC_URL", "http://localhost:8001")
    agent_registry_url: str = os.getenv("AGENT_REGISTRY_URL", "http://agent-registry:8080")
    request_timeout_seconds: float = float(os.getenv("AGENT_REQUEST_TIMEOUT_SECONDS", "30"))
    max_retries: int = int(os.getenv("AGENT_MAX_RETRIES", "2"))
    aws_agent_enabled: bool = os.getenv("AWS_AGENT_ENABLED", "false").lower() == "true"
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()
