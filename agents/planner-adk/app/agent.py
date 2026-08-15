"""Planner Agent — orchestration logic.

Implements the execution states from PROJECT_SPEC.md §12:
RECEIVED -> DISCOVERING_AGENTS -> DELEGATING -> WAITING_SPECIALISTS ->
CALCULATING_BUDGET -> OPTIONAL_ENRICHMENT -> CONSOLIDATING ->
COMPLETED | PARTIAL | FAILED

Fase 2 scope (PROJECT_SPEC.md §43): the real Flight Agent now exists and
is called for real over A2A; Hotel/Activity/Budget/Enrichment
(§5.3-§5.6) still don't, so this module keeps applying the documented
degradation rules (§11) for those:

  hotel/activities -> status UNAVAILABLE, overall response PARTIAL
  budget -> status UNKNOWN (per §11 "Budget indisponível")
  enrichment -> status SKIPPED (AWS agent optional/off by default)

Real specialists are wired in incrementally per §43 Fase 3-5, without
changing this module's public contract.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

from opentelemetry import trace

from .a2a.client import A2AClient, A2AClientError
from .a2a.models import Message, Task, TaskStatus, TextPart
from .config import settings
from .registry_client import RegistryClient
from .schemas import (
    ActivityResult,
    BudgetResult,
    EnrichmentResult,
    FlightResult,
    HotelResult,
    TravelRequest,
    TravelResponse,
    TravelResponseMetadata,
)

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

registry_client = RegistryClient(settings.agent_registry_url)
a2a_client = A2AClient(timeout_seconds=settings.request_timeout_seconds)


def _log_state(request_id: str, state: str) -> None:
    logger.info(
        "planner state transition",
        extra={"event": "state_transition", "request_id": request_id, "correlation_id": request_id},
    )
    logger.info(f"state={state}", extra={"request_id": request_id, "correlation_id": request_id})


async def discover_agents() -> list[dict[str, Any]]:
    """Registry + Agent Card discovery (§9). Never hard-code capabilities."""
    with tracer.start_as_current_span("registry.discovery"):
        try:
            return await registry_client.list_agents()
        except Exception as exc:  # noqa: BLE001
            logger.warning("agent registry unreachable: %s", exc)
            return []


async def _delegate_to_agent(agent: dict[str, Any], text: str, context_id: str) -> dict[str, Any] | None:
    span_name = f"a2a.{agent.get('id', 'unknown')}"
    with tracer.start_as_current_span(span_name):
        try:
            return await a2a_client.send_text(agent["url"], text, context_id=context_id)
        except (A2AClientError, Exception) as exc:  # noqa: BLE001
            logger.warning("delegation to %s failed: %s", agent.get("id"), exc)
            return None


# Minimal valid payload used for the foundation check: generic enough that
# mock-specialist-agent just echoes it, but also a well-formed enough
# TravelRequest subset that flight-agent (which validates required fields)
# accepts it too.
_FOUNDATION_CHECK_PAYLOAD = json.dumps(
    {
        "origin": "GRU",
        "destination": "FLN",
        "start_date": "2026-01-01",
        "end_date": "2026-01-02",
        "travelers": 1,
    }
)


async def run_foundation_check() -> dict[str, Any]:
    """Acceptance check: Registry discovery + A2A round-trip to every
    registered agent. Used by /v1/foundation-check and the E2E test.
    """
    request_id = str(uuid.uuid4())
    _log_state(request_id, "RECEIVED")

    _log_state(request_id, "DISCOVERING_AGENTS")
    agents = await discover_agents()

    _log_state(request_id, "DELEGATING")
    results = {}
    for agent in agents:
        result = await _delegate_to_agent(agent, _FOUNDATION_CHECK_PAYLOAD, request_id)
        results[agent["id"]] = result

    _log_state(request_id, "CONSOLIDATING")
    status = "COMPLETED" if agents and all(r is not None for r in results.values()) else "PARTIAL"
    _log_state(request_id, status)

    return {
        "request_id": request_id,
        "status": status,
        "discovered_agents": [a["id"] for a in agents],
        "delegation_results": results,
    }


def _parse_flight_result(task: dict[str, Any] | None) -> FlightResult:
    """Parses the Task returned by flight-agent's `search_flights` skill
    into a FlightResult. Never fabricates flight data (§31): any parsing
    failure or missing task degrades to UNAVAILABLE, never a guess.
    """
    if task is None:
        return FlightResult(status="UNAVAILABLE", notes="flight-agent unreachable")
    try:
        message = task["status"]["message"]
        text = next(p["text"] for p in message["parts"] if p.get("kind") == "text")
        raw = json.loads(text)
        return FlightResult.model_validate(raw)
    except Exception as exc:  # noqa: BLE001
        logger.warning("failed to parse flight-agent response: %s", exc)
        return FlightResult(status="UNAVAILABLE", notes=f"invalid flight-agent response: {exc}")


async def handle_travel_request(payload: TravelRequest) -> TravelResponse:
    start = time.perf_counter()
    request_id = payload.request_id or str(uuid.uuid4())
    span = trace.get_current_span()
    ctx = span.get_span_context() if span else None
    trace_id = format(ctx.trace_id, "032x") if ctx and ctx.is_valid else str(uuid.uuid4())

    _log_state(request_id, "RECEIVED")

    _log_state(request_id, "DISCOVERING_AGENTS")
    agents = await discover_agents()

    _log_state(request_id, "DELEGATING")
    delegation_text = json.dumps(payload.model_dump())
    delegation_results: dict[str, dict[str, Any] | None] = {}
    for agent in agents:
        delegation_results[agent["id"]] = await _delegate_to_agent(agent, delegation_text, request_id)

    _log_state(request_id, "WAITING_SPECIALISTS")
    flight = _parse_flight_result(delegation_results.get("flight-agent"))
    # Hotel/Activity specialists are not implemented yet (Fase 3-4).
    # Per §11, an unavailable specialist yields a PARTIAL overall response.
    hotel = HotelResult(status="UNAVAILABLE", notes="hotel-agent not implemented yet (planned for Fase 3)")
    activities = ActivityResult(status="UNAVAILABLE", notes="activity-agent not implemented yet (planned for Fase 4)")

    _log_state(request_id, "CALCULATING_BUDGET")
    # Budget specialist not implemented yet -> §11 "Budget indisponível" rule.
    budget = BudgetResult(status="UNAVAILABLE", budget_status="UNKNOWN", limit=payload.budget)

    _log_state(request_id, "OPTIONAL_ENRICHMENT")
    enrichment = EnrichmentResult(status="SKIPPED", provider=None)
    if settings.aws_agent_enabled:
        # AWS Enrichment agent is optional and never on the critical path (§5.6).
        enrichment = EnrichmentResult(status="UNAVAILABLE", provider=None)

    _log_state(request_id, "CONSOLIDATING")
    overall_status = "PARTIAL"
    _log_state(request_id, overall_status)

    duration_ms = (time.perf_counter() - start) * 1000
    return TravelResponse(
        request_id=request_id,
        status=overall_status,
        flight=flight,
        hotel=hotel,
        activities=activities,
        budget=budget,
        enrichment=enrichment,
        metadata=TravelResponseMetadata(trace_id=trace_id, correlation_id=request_id, duration_ms=duration_ms),
    )


async def handle_a2a_message(message: Message) -> Task:
    """Allows the Planner to also be addressed over A2A (e.g. by a future
    gateway agent), reusing the same orchestration logic as the HTTP API.
    """
    text = " ".join(p.text for p in message.parts if getattr(p, "kind", None) == "text")
    try:
        raw = json.loads(text)
        travel_request = TravelRequest.model_validate(raw)
    except Exception as exc:  # noqa: BLE001
        reply = Message(
            role="agent",
            parts=[TextPart(text=f"invalid TravelRequest payload: {exc}")],
            context_id=message.context_id,
        )
        return Task(
            context_id=message.context_id or "unknown",
            status=TaskStatus(state="failed", message=reply),
            history=[message, reply],
        )

    response = await handle_travel_request(travel_request)
    reply = Message(
        role="agent",
        parts=[TextPart(text=response.model_dump_json())],
        context_id=message.context_id,
    )
    return Task(
        context_id=message.context_id or response.request_id,
        status=TaskStatus(state="completed", message=reply),
        history=[message, reply],
    )
