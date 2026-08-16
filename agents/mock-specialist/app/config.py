from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    service_name: str = os.getenv("SERVICE_NAME", "mock-specialist-agent")
    port: int = int(os.getenv("PORT", "8099"))
    public_url: str = os.getenv("PUBLIC_URL", "http://localhost:8099")
    # Fase 9 (§7/§56 "M6 Security"): see app/auth.py for what each
    # mode does. "dev" (spec default) requires DEV_AGENT_TOKEN on every
    # /a2a call; "jwt" requires a valid HS256 JWT instead.
    auth_mode: str = os.getenv("AUTH_MODE", "dev")
    dev_agent_token: str = os.getenv("DEV_AGENT_TOKEN", "local-development-only")
    jwt_secret: str = os.getenv("JWT_SECRET", "local-development-only-change-me")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()
