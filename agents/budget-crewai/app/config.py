from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    service_name: str = os.getenv("SERVICE_NAME", "budget-agent")
    port: int = int(os.getenv("PORT", "8005"))
    public_url: str = os.getenv("PUBLIC_URL", "http://localhost:8005")
    # Defaults match docker-compose.yml's overrides (which include the
    # /mcp path the Streamable HTTP servers actually serve on) — without
    # it here, running this agent outside compose silently pointed at the
    # wrong path.
    mcp_currency_url: str = os.getenv("MCP_CURRENCY_URL", "http://mcp-currency:9005/mcp")
    mcp_calculator_url: str = os.getenv("MCP_CALCULATOR_URL", "http://mcp-calculator:9006/mcp")
    request_timeout_seconds: float = float(os.getenv("AGENT_REQUEST_TIMEOUT_SECONDS", "30"))
    # Heuristic per-traveler-per-night estimates (BRL), used because no
    # food/transport pricing MCP was specified in PROJECT_SPEC.md §33 —
    # the contract fields themselves are named "*_estimate", not "*_cost".
    food_per_traveler_per_night: float = float(os.getenv("BUDGET_FOOD_PER_TRAVELER_PER_NIGHT", "120"))
    transport_per_traveler_per_night: float = float(os.getenv("BUDGET_TRANSPORT_PER_TRAVELER_PER_NIGHT", "60"))
    # Optional: only used by the CrewAI-driven path (see app/agent.py and
    # docs/adr/ADR-012-budget-agent-crewai-optional.md).
    crewai_llm_model: str = os.getenv("CREWAI_LLM_MODEL", "")
    # Fase 9 (§7/§56 "M6 Security"): see app/auth.py for what each
    # mode does. "dev" (spec default) requires DEV_AGENT_TOKEN on every
    # /a2a call; "jwt" requires a valid HS256 JWT instead.
    auth_mode: str = os.getenv("AUTH_MODE", "dev")
    dev_agent_token: str = os.getenv("DEV_AGENT_TOKEN", "local-development-only")
    jwt_secret: str = os.getenv("JWT_SECRET", "local-development-only-change-me")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()
