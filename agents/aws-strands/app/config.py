from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    service_name: str = os.getenv("SERVICE_NAME", "aws-enrichment-agent")
    port: int = int(os.getenv("PORT", "8006"))
    public_url: str = os.getenv("PUBLIC_URL", "http://localhost:8006")
    # Default matches docker-compose.yml's override (which includes the
    # /mcp path the Streamable HTTP server actually serves on) — without
    # it here, running this agent outside compose silently pointed at the
    # wrong path.
    mcp_weather_url: str = os.getenv("MCP_WEATHER_URL", "http://mcp-weather:9004/mcp")
    request_timeout_seconds: float = float(os.getenv("AGENT_REQUEST_TIMEOUT_SECONDS", "30"))
    # Optional: only used by the Strands-driven path (see app/agent.py and
    # docs/adr/ADR-013-enrichment-agent-strands-optional.md). Empty/unknown
    # value (the default) means the deterministic path always runs — this
    # is what keeps this agent free-by-default and testable in CI without
    # a live Ollama/Bedrock (PROJECT_SPEC.md §5.6 provider config table).
    model_provider: str = os.getenv("MODEL_PROVIDER", "").strip().lower()
    ollama_host: str = os.getenv("OLLAMA_HOST", "http://ollama:11434")
    ollama_model_id: str = os.getenv("OLLAMA_MODEL_ID", "llama3.1")
    bedrock_model_id: str = os.getenv("BEDROCK_MODEL_ID", "us.amazon.nova-lite-v1:0")
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()
