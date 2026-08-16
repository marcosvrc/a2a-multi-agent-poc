FROM python:3.11-slim

WORKDIR /app

# The CrewAI-driven optional path (ADR-012, gated by CREWAI_LLM_MODEL) is
# only reachable if the `crewai` extra is actually installed — previously
# this Dockerfile never installed it, so the optional path silently
# no-op'd (fell back to deterministic) in every container regardless of
# CREWAI_LLM_MODEL. Kept as a build arg rather than unconditional (like
# activity-beeai's `beeai` extra) since crewai is a heavy dependency not
# needed by the default deterministic path or by CI/tests.
ARG INSTALL_CREWAI=false

COPY pyproject.toml .
RUN pip install --no-cache-dir fastapi==0.115.6 "uvicorn[standard]==0.32.1" httpx==0.28.1 \
    pydantic==2.12.3 opentelemetry-sdk==1.29.0 \
    opentelemetry-exporter-otlp-proto-grpc==1.29.0 \
    opentelemetry-instrumentation-fastapi==0.50b0 \
    mcp==1.27.0 && \
    if [ "$INSTALL_CREWAI" = "true" ]; then pip install --no-cache-dir "crewai==0.98.0"; fi

COPY app ./app

ENV PORT=8005
EXPOSE 8005

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
