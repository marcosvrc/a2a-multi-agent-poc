from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    service_name: str = os.getenv("SERVICE_NAME", "mock-specialist-agent")
    port: int = int(os.getenv("PORT", "8099"))
    public_url: str = os.getenv("PUBLIC_URL", "http://localhost:8099")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()
