FROM python:3.11-slim

WORKDIR /app

# The Strands-driven optional path (ADR-013, gated by MODEL_PROVIDER) is
# only reachable if the `strands` extra is actually installed — same
# pattern as budget-crewai's ARG INSTALL_CREWAI. Kept as a build arg
# rather than unconditional since strands-agents is a heavy dependency
# not needed by the default deterministic path or by CI/tests.
ARG INSTALL_STRANDS=false

COPY pyproject.toml .
RUN pip install --no-cache-dir fastapi==0.115.6 "uvicorn[standard]==0.32.1" httpx==0.28.1 \
    pydantic==2.12.3 opentelemetry-sdk==1.29.0 \
    opentelemetry-exporter-otlp-proto-grpc==1.29.0 \
    opentelemetry-instrumentation-fastapi==0.50b0 \
    mcp==1.27.0 && \
    if [ "$INSTALL_STRANDS" = "true" ]; then pip install --no-cache-dir "strands-agents==1.52.0"; fi

COPY app ./app

ENV PORT=8006
EXPOSE 8006

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
