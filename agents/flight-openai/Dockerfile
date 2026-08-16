FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir fastapi==0.115.6 "uvicorn[standard]==0.32.1" httpx==0.28.1 \
    pydantic==2.12.3 opentelemetry-sdk==1.29.0 \
    opentelemetry-exporter-otlp-proto-grpc==1.29.0 \
    opentelemetry-instrumentation-fastapi==0.50b0 \
    pyjwt==2.10.1 \
    mcp==1.27.0 openai-agents==0.21.0

COPY app ./app

ENV PORT=8002
EXPOSE 8002

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
