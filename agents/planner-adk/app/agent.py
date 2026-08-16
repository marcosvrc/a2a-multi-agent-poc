"""Planner Agent — orchestration logic.

Implements the execution states from PROJECT_SPEC.md §12:
RECEIVED -> DISCOVERING_AGENTS -> DELEGATING -> WAITING_SPECIALISTS ->
CALCULATING_BUDGET -> OPTIONAL_ENRICHMENT -> CONSOLIDATING ->
COMPLETED | PARTIAL | FAILED

Fase 5 scope (PROJECT_SPEC.md §43): Flight, Hotel, Activity and Budget
are real specialists called over A2A (flight-agent in Python/OpenAI
Agents SDK, hotel-agent in TypeScript/LangGraph, activity-agent in
Python/BeeAI Framework, budget-agent in Python/CrewAI — proving A2A
interoperability across languages and frameworks).

Fase 6 scope (§43 "Paralelismo"): Flight, Hotel and Activity are now
delegated concurrently (`asyncio.gather`) instead of one after another —
they're independent of each other, so there's no reason WAITING_SPECIALISTS
should take as long as the sum of all three round-trips. Budget still
can't join that fan-out: per §5.5 it needs their *results*, not the raw
TravelRequest, so it stays sequenced after (see `_delegate_budget`).
Agent Card discovery (`_agents_by_skill`) is likewise fetched concurrently
now, for the same reason — nothing about DISCOVERING_AGENTS requires
fetching one agent's card before starting the next.

Fase 7 scope (§5.6/§43 "AWS"): the AWS Enrichment Agent
(agents/aws-strands, AWS Strands Agents SDK) is now a real, optional
fifth specialist, delegated by `_delegate_enrichment` — same
skill-based discovery as the other four, but only attempted at all when
`AWS_AGENT_ENABLED=true` (§11: "AWS Enrichment indisponível: Ignorar.
Não marcar o fluxo como falha" — this is why `enrichment` stays excluded
from the COMPLETED/PARTIAL/FAILED calculation below, unlike the four
core specialists).

Fase 8 scope (§27/§35 "Resiliência"): A2A calls now retry transient
transport failures with exponential backoff (`A2AClient`, see
app/a2a/client.py) and are additionally guarded by a per-agent circuit
breaker (`app/resilience.py`) — a specialist that keeps failing stops
being retried on every single request once its breaker OPENs, instead
of costing a full timeout each time. Budget specifically reports
`status=UNKNOWN` (not `UNAVAILABLE`) on failure, per §35 CT-R06 — every
other specialist's failure/unreachable case still reports
`UNAVAILABLE`, matching CT-R01/CT-R05.

Real specialists are wired in incrementally per §43 Fase 9, without
changing this module's public contract.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from datetime import date
from typing import Any

from opentelemetry import trace

from .a2a.client import A2AClient, A2AClientError
from .a2a.models import Message, Task, TaskStatus, TextPart
from .config import settings
from .registry_client import RegistryClient
from .resilience import CircuitBreakerRegistry
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
a2a_client = A2AClient(
    timeout_seconds=settings.request_timeout_seconds,
    retry_attempts=settings.max_retries,
    retry_backoff_base_seconds=settings.retry_backoff_base_seconds,
)
# One circuit breaker per discovered agent id (§27/§35, Fase 8) — shared
# across Agent Card fetches and A2A delegation, since both are calls to
# the same downstream agent and a definitely-down agent shouldn't be
# retried-into on either path.
circuit_breakers = CircuitBreakerRegistry(
    failure_threshold=settings.circuit_breaker_failure_threshold,
    reset_timeout_seconds=settings.circuit_breaker_reset_timeout_seconds,
)

# Skill ids declared by each specialist's own Agent Card (see e.g.
# flight-openai/app/a2a/agent_card.py, hotel-langgraph/src/a2a/agentCard.ts).
# §9 ("Não fazer hard-code de capabilities no Planner") means the Planner
# must not assume a specific agent-id string like "flight-agent" is the
# flight specialist — only the skill id, declared by the agent itself, is
# a legitimate source of truth for what an agent can do. These constants
# name the *skills* the Planner looks for, not agents.
_SKILL_FLIGHT = "search_flights"
_SKILL_HOTEL = "search_hotels"
_SKILL_ACTIVITY = "plan_activities"
_SKILL_BUDGET = "calculate_budget"
_SKILL_ENRICHMENT = "enrich_destination"


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


async def _fetch_agent_card(agent: dict[str, Any]) -> Any | None:
    agent_id = agent.get("id", "unknown")
    breaker = circuit_breakers.get(agent_id)
    if not breaker.allow_request():
        logger.warning("circuit breaker OPEN for %s, skipping Agent Card fetch", agent_id)
        return None
    try:
        card = await a2a_client.get_agent_card(agent["url"])
    except Exception as exc:  # noqa: BLE001
        logger.warning("failed to fetch agent card for %s: %s", agent_id, exc)
        breaker.record_failure()
        return None
    breaker.record_success()
    return card


async def _agents_by_skill(agents: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Fetches each discovered agent's Agent Card and indexes agents by
    skill id (§9: Agent Card discovery, not hard-coded agent-id string
    matching, is how the Planner is supposed to find "the flight
    specialist" etc). If two agents ever advertised the same skill, the
    first one discovered wins — out of scope for this POC to disambiguate
    further. An agent whose card can't be fetched or parsed is dropped
    silently (never a guess, §31) rather than assumed to have any skill.

    Cards are fetched concurrently (Fase 6 "Paralelismo") — one agent's
    card being slow to respond shouldn't hold up discovering every other
    agent's skills.
    """
    cards = await asyncio.gather(*(_fetch_agent_card(agent) for agent in agents))

    result: dict[str, dict[str, Any]] = {}
    for agent, card in zip(agents, cards):
        if card is None:
            continue
        for skill in card.skills:
            result.setdefault(skill.id, agent)
    return result


async def _delegate_to_agent(agent: dict[str, Any], text: str, context_id: str) -> dict[str, Any] | None:
    agent_id = agent.get("id", "unknown")
    breaker = circuit_breakers.get(agent_id)
    if not breaker.allow_request():
        # §27/§35 (Fase 8): a specialist that has already failed
        # `circuit_breaker_failure_threshold` times in a row is skipped
        # outright — no network round-trip, no timeout to wait out —
        # until the cooldown elapses. This degrades exactly like an
        # unreachable agent (None -> UNAVAILABLE/UNKNOWN downstream via
        # _parse_specialist_result), just without paying for the retry
        # budget on every single request in between.
        logger.warning("circuit breaker OPEN for %s, skipping delegation", agent_id)
        return None
    span_name = f"a2a.{agent_id}"
    with tracer.start_as_current_span(span_name):
        try:
            result = await a2a_client.send_text(agent["url"], text, context_id=context_id)
        except (A2AClientError, Exception) as exc:  # noqa: BLE001
            logger.warning("delegation to %s failed: %s", agent_id, exc)
            breaker.record_failure()
            return None
    breaker.record_success()
    return result


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
    outcomes = await asyncio.gather(
        *(_delegate_to_agent(agent, _FOUNDATION_CHECK_PAYLOAD, request_id) for agent in agents)
    )
    results = {agent["id"]: outcome for agent, outcome in zip(agents, outcomes)}

    _log_state(request_id, "CONSOLIDATING")
    status = "COMPLETED" if agents and all(r is not None for r in results.values()) else "PARTIAL"
    _log_state(request_id, status)

    return {
        "request_id": request_id,
        "status": status,
        "discovered_agents": [a["id"] for a in agents],
        "delegation_results": results,
    }


def _extract_text(message: dict[str, Any] | None) -> str | None:
    if not message:
        return None
    try:
        return next(p["text"] for p in message["parts"] if p.get("kind") == "text")
    except (KeyError, StopIteration, TypeError):
        return None


def _parse_specialist_result(
    agent_id: str,
    task: dict[str, Any] | None,
    model_cls: type,
    *,
    unavailable_status: str = "UNAVAILABLE",
) -> Any:
    """Parses the Task returned by a specialist's A2A skill into the given
    result model. Never fabricates data (§31): any parsing failure or
    missing task degrades to `unavailable_status`, never a guess. Shared
    by all five real specialists (Python and TypeScript alike — the wire
    format is identical, per the A2A adapter contract).

    `unavailable_status` defaults to "UNAVAILABLE" (flight/hotel/activity/
    enrichment, §35 CT-R01/CT-R05) but Budget passes "UNKNOWN" instead
    (§35 CT-R06: "Budget falha -> PARTIAL, budget.status=UNKNOWN") — both
    are honest ways of saying "no real result", the wording is just
    domain-specific to what each specialist represents.
    """
    if task is None:
        return model_cls(status=unavailable_status, notes=f"{agent_id} unreachable")

    try:
        state = task["status"]["state"]
    except (KeyError, TypeError) as exc:
        logger.warning("malformed task from %s: %s", agent_id, exc)
        return model_cls(status=unavailable_status, notes=f"malformed {agent_id} task: {exc}")

    if state in ("failed", "canceled"):
        # A terminal-but-unsuccessful task state is itself the specialist
        # telling us it couldn't complete — trust that signal instead of
        # trying to parse whatever message it attached as if it were a
        # real result (the previous code ignored `state` entirely and
        # would happily try to json.loads() a failure explanation).
        reason = _extract_text(task.get("status", {}).get("message"))
        notes = f"{agent_id} task {state}" + (f": {reason}" if reason else "")
        return model_cls(status=unavailable_status, notes=notes)

    if state != "completed":
        # submitted/working/input-required: non-terminal. This Planner
        # only does synchronous message/send today (no tasks/get polling
        # yet — that's a later Fase), so a non-terminal state here means
        # the specialist simply hadn't finished by the time it replied;
        # degrade explicitly rather than mis-parsing an in-progress
        # status as if it were the final result.
        return model_cls(status=unavailable_status, notes=f"{agent_id} task not completed (state={state})")

    try:
        text = _extract_text(task["status"]["message"])
        if text is None:
            raise ValueError("completed task has no text part")
        raw = json.loads(text)
        return model_cls.model_validate(raw)
    except Exception as exc:  # noqa: BLE001
        logger.warning("failed to parse %s response: %s", agent_id, exc)
        return model_cls(status=unavailable_status, notes=f"invalid {agent_id} response: {exc}")


def _nights_between(start_date: str, end_date: str) -> int:
    try:
        delta = (date.fromisoformat(end_date) - date.fromisoformat(start_date)).days
    except ValueError:
        return 1
    return max(delta, 1)


async def _delegate_budget(
    skill_agents: dict[str, dict[str, Any]],
    payload: TravelRequest,
    flight: FlightResult,
    hotel: HotelResult,
    activities: ActivityResult,
    request_id: str,
) -> BudgetResult:
    """Budget is delegated after (not alongside) flight/hotel/activity,
    since §5.5 requires their *results*, not the raw TravelRequest.

    §35 CT-R06 ("Budget falha -> PARTIAL, budget.status=UNKNOWN"): unlike
    the other three core specialists, Budget's own failure/unreachable
    status is UNKNOWN, not UNAVAILABLE — see _parse_specialist_result's
    unavailable_status param below.
    """
    budget_agent = skill_agents.get(_SKILL_BUDGET)
    if budget_agent is None:
        return BudgetResult(
            status="UNKNOWN",
            budget_status="UNKNOWN",
            limit=payload.budget,
            notes="no agent advertising the calculate_budget skill",
        )

    budget_payload = json.dumps(
        {
            "request_id": request_id,
            "budget_limit": payload.budget,
            "currency": payload.currency,
            "travelers": payload.travelers,
            "nights": _nights_between(payload.start_date, payload.end_date),
            "flight": flight.model_dump(),
            "hotel": hotel.model_dump(),
            "activities": activities.model_dump(),
        }
    )
    task = await _delegate_to_agent(budget_agent, budget_payload, request_id)
    return _parse_specialist_result("budget-agent", task, BudgetResult, unavailable_status="UNKNOWN")


async def _delegate_enrichment(
    skill_agents: dict[str, dict[str, Any]],
    payload: TravelRequest,
    request_id: str,
) -> EnrichmentResult:
    """§5.6/§11: entirely optional and never on the critical path. Unlike
    flight/hotel/activity/budget, this specialist isn't even attempted
    unless AWS_AGENT_ENABLED=true — with it false (the default), the
    Planner doesn't try to discover or call an enrichment skill at all,
    matching §37's acceptance criterion that the AWS agent "puder ficar
    desligado" without any other behavior change.
    """
    if not settings.aws_agent_enabled:
        return EnrichmentResult(status="SKIPPED", provider=None)

    enrichment_agent = skill_agents.get(_SKILL_ENRICHMENT)
    if enrichment_agent is None:
        return EnrichmentResult(status="UNAVAILABLE", provider=None)

    enrichment_payload = json.dumps(
        {
            "request_id": request_id,
            "destination": payload.destination,
            "start_date": payload.start_date,
            "end_date": payload.end_date,
            "preferences": payload.preferences,
        }
    )
    task = await _delegate_to_agent(enrichment_agent, enrichment_payload, request_id)
    return _parse_specialist_result("aws-enrichment-agent", task, EnrichmentResult)


async def handle_travel_request(payload: TravelRequest) -> TravelResponse:
    start = time.perf_counter()
    request_id = payload.request_id or str(uuid.uuid4())
    span = trace.get_current_span()
    ctx = span.get_span_context() if span else None
    trace_id = format(ctx.trace_id, "032x") if ctx and ctx.is_valid else str(uuid.uuid4())

    _log_state(request_id, "RECEIVED")

    _log_state(request_id, "DISCOVERING_AGENTS")
    agents = await discover_agents()
    # Select specialists by declared skill, not by assuming a specific
    # agent-id string (§9) — see _agents_by_skill.
    skill_agents = await _agents_by_skill(agents)

    _log_state(request_id, "DELEGATING")
    # Send the Planner-generated request_id downstream (the incoming
    # payload's own request_id may be null — TravelRequest makes it
    # optional while contracts/schemas/travel-request.schema.json requires
    # it) so specialists/logs/traces can all be correlated by the same id
    # the Planner itself reports in its response metadata.
    delegation_payload = payload.model_dump()
    delegation_payload["request_id"] = request_id
    delegation_text = json.dumps(delegation_payload)

    # Flight/Hotel/Activity are independent of one another — nothing about
    # one specialist's answer feeds another's request — so they're fanned
    # out concurrently (§43 Fase 6 "Paralelismo") instead of one after
    # another. Budget is excluded here on purpose: per §5.5 it needs their
    # *results*, so it can only run after this fan-out completes (see
    # _delegate_budget, called below once WAITING_SPECIALISTS is done).
    _delegation_targets = (
        (_SKILL_FLIGHT, "flight-agent"),
        (_SKILL_HOTEL, "hotel-agent"),
        (_SKILL_ACTIVITY, "activity-agent"),
    )

    async def _delegate_if_present(skill_id: str) -> dict[str, Any] | None:
        agent = skill_agents.get(skill_id)
        if agent is None:
            return None
        return await _delegate_to_agent(agent, delegation_text, request_id)

    delegation_outcomes = await asyncio.gather(
        *(_delegate_if_present(skill_id) for skill_id, _ in _delegation_targets)
    )
    delegation_results: dict[str, dict[str, Any] | None] = dict(
        zip((label for _, label in _delegation_targets), delegation_outcomes)
    )

    _log_state(request_id, "WAITING_SPECIALISTS")
    flight = _parse_specialist_result("flight-agent", delegation_results.get("flight-agent"), FlightResult)
    hotel = _parse_specialist_result("hotel-agent", delegation_results.get("hotel-agent"), HotelResult)
    activities = _parse_specialist_result("activity-agent", delegation_results.get("activity-agent"), ActivityResult)

    _log_state(request_id, "CALCULATING_BUDGET")
    budget = await _delegate_budget(skill_agents, payload, flight, hotel, activities, request_id)

    _log_state(request_id, "OPTIONAL_ENRICHMENT")
    enrichment = await _delegate_enrichment(skill_agents, payload, request_id)

    _log_state(request_id, "CONSOLIDATING")
    # Enrichment is intentionally excluded: it is optional and never on
    # the critical path (§5.6), so SKIPPED must not prevent COMPLETED.
    core_results = (flight, hotel, activities, budget)
    successes = sum(1 for r in core_results if r.status == "SUCCESS")
    if successes == len(core_results):
        overall_status = "COMPLETED"
    elif successes == 0:
        # Every core specialist failed (e.g. the agent registry was empty
        # or fully unreachable) — PARTIAL is documented for individual
        # specialist degradation (§11) but would misleadingly imply some
        # real data was obtained when none was. FAILED is a valid
        # TravelResponse.status value that this branch previously never
        # produced.
        overall_status = "FAILED"
    else:
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
