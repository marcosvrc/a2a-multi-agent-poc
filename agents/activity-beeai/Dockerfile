FROM python:3.11-slim

WORKDIR /app

# The BeeAI-driven optional path (ADR-011, gated by BEEAI_CHAT_MODEL) is
# only reachable if the `beeai` extra is actually installed — this
# Dockerfile never installed it before, so BEEAI_CHAT_MODEL silently
# no-op'd (ImportError caught, falls back to deterministic) in every
# container regardless of the env var. Kept as a build arg rather than
# unconditional (same pattern as budget-crewai's INSTALL_CREWAI /
# aws-strands's INSTALL_STRANDS) since beeai-framework is a heavy
# dependency not needed by the default deterministic path or by CI/tests.
ARG INSTALL_BEEAI=false

COPY pyproject.toml .
RUN pip install --no-cache-dir fastapi==0.115.6 "uvicorn[standard]==0.32.1" httpx==0.28.1 \
    pydantic==2.12.3 opentelemetry-sdk==1.29.0 \
    opentelemetry-exporter-otlp-proto-grpc==1.29.0 \
    opentelemetry-instrumentation-fastapi==0.50b0 \
    pyjwt==2.10.1 \
    mcp==1.27.0 && \
    if [ "$INSTALL_BEEAI" = "true" ]; then pip install --no-cache-dir "beeai-framework==0.1.82"; fi

COPY app ./app

ENV PORT=8004
EXPOSE 8004

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
