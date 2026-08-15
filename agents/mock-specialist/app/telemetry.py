"""OpenTelemetry bootstrap shared shape across all Python agents.

Each agent configures its own service.name but the wiring is identical:
OTLP gRPC exporter pointed at the local otel-collector, batch processor,
FastAPI auto-instrumentation, plus a structured JSON logger that always
includes trace_id / span_id / request_id / correlation_id when available.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from typing import Any

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_NAMESPACE, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        span = trace.get_current_span()
        ctx = span.get_span_context() if span else None
        payload: dict[str, Any] = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "service": os.getenv("SERVICE_NAME", "unknown-service"),
            "message": record.getMessage(),
        }
        if ctx and ctx.is_valid:
            payload["trace_id"] = format(ctx.trace_id, "032x")
            payload["span_id"] = format(ctx.span_id, "016x")
        for key in ("request_id", "correlation_id", "target_agent", "event"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        return json.dumps(payload)


def setup_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(os.getenv("LOG_LEVEL", "INFO"))


def setup_tracing(app: Any) -> None:
    if os.getenv("OTEL_SDK_DISABLED", "false").lower() == "true":
        # Standard OTel env var; used to keep unit tests fast/offline
        # (no background exporter thread trying to reach a collector).
        FastAPIInstrumentor.instrument_app(app)
        return

    service_name = os.getenv("SERVICE_NAME", "unknown-service")
    namespace = os.getenv("OTEL_SERVICE_NAMESPACE", "a2a-poc")
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")

    resource = Resource.create({SERVICE_NAME: service_name, SERVICE_NAMESPACE: namespace})
    provider = TracerProvider(resource=resource)
    try:
        exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    except Exception:  # noqa: BLE001 — tracing must never block the app
        logging.getLogger(__name__).warning("failed to configure OTLP exporter at %s", endpoint)
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)


def get_tracer(name: str):
    return trace.get_tracer(name)
