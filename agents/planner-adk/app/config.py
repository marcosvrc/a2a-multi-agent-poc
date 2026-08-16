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
    # §27: "retry: 2, backoff: exponential" — max_retries was already
    # scaffolded (Fase 0) but never actually wired into the A2A client
    # until Fase 8; now used by A2AClient's transient-failure retry.
    max_retries: int = int(os.getenv("AGENT_MAX_RETRIES", "2"))
    retry_backoff_base_seconds: float = float(os.getenv("AGENT_RETRY_BACKOFF_BASE_SECONDS", "0.5"))
    # Fase 8 (§27/§35): per-agent circuit breaker in front of A2A
    # delegation — see app/resilience.py.
    circuit_breaker_failure_threshold: int = int(os.getenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "3"))
    circuit_breaker_reset_timeout_seconds: float = float(
        os.getenv("CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS", "30")
    )
    aws_agent_enabled: bool = os.getenv("AWS_AGENT_ENABLED", "false").lower() == "true"
    # Fase 9 (§7/§56 "M6 Security"): see app/auth.py for what each mode
    # does. "dev" (spec default) requires DEV_AGENT_TOKEN on every /a2a
    # call; "jwt" requires a valid HS256 JWT instead and carries this
    # agent's own identity as the `sub` claim on outgoing calls.
    auth_mode: str = os.getenv("AUTH_MODE", "dev")
    dev_agent_token: str = os.getenv("DEV_AGENT_TOKEN", "local-development-only")
    jwt_secret: str = os.getenv("JWT_SECRET", "local-development-only-change-me")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()
