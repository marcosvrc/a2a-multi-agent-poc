"""Budget Agent — business logic (PROJECT_SPEC.md §5.5).

Unlike flight/hotel/activity, this agent does not search anything: the
Planner delegates it the *results* of the other three specialists plus
the traveler's maximum budget (see planner-adk/app/agent.py,
`_delegate_budget`), and this agent only combines numbers.

Two execution paths, mirroring ADR-009 (flight) and ADR-011 (activity):

- Deterministic (default, used whenever CREWAI_LLM_MODEL is not set):
  pulls flight/hotel/activity costs out of the given results, adds
  food/transport heuristics (§5.5 fields are explicitly named
  "*_estimate", not "*_cost" — no pricing MCP was specified for those),
  and combines everything exclusively through MCP Calculator tool calls
  (`sum`/`subtract`/`multiply`) — never a local `eval` or ad-hoc
  arithmetic expression, per §33 ("Não permitir expressão arbitrária
  executada via eval"). When the traveler's currency differs from the
  BRL the mock flight/hotel data is priced in, every component is
  converted via MCP Currency first.
- CrewAI-driven (only when CREWAI_LLM_MODEL is set): would run a CrewAI
  `Crew` with one `Agent`/`Task` wired to the same MCP Currency/
  Calculator tools. See ADR-012: not exercised by this milestone's
  automated tests (no LLM backend available in CI/dev by default), and
  falls back to the deterministic path on any failure.

Never fabricates a total (§31): every cost component either traces back
to a real flight/hotel/activity result the Planner already validated, a
fixed documented heuristic (food/transport estimates), or a real MCP
Calculator/Currency call. If a cost component is unavailable, it is
treated as zero and noted — it never silently blocks the rest of the
calculation (§5.5's implicit "best effort" contract, matching how
flight/hotel/activity already degrade individually).
"""
from __future__ import annotations

import asyncio
import json
import logging

from opentelemetry import trace

from .a2a.models import Message, Task, TaskStatus, TextPart
from .config import settings
from .mcp_client import McpToolError, calc_multiply, calc_subtract, calc_sum, convert_currency

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

# BRL, per item, flat estimate — the ActivityResult schema carries no
# price field (mcp-places is a points-of-interest catalog, not a pricing
# API), so a fixed table is the only non-fabricated way to attach a cost
# to each category, analogous to the duration table in mcp/places.
_ACTIVITY_COST_TABLE = {
    "sightseeing": 40.0,
    "museum": 60.0,
    "beach": 20.0,
    "hiking": 30.0,
    "food": 80.0,
    "shopping": 100.0,
    "nightlife": 120.0,
    "culture": 50.0,
}
_DEFAULT_ACTIVITY_ITEM_COST = 50.0


async def _calc_sum_all(mcp_url: str, values: list[float], timeout_seconds: float) -> float:
    total = 0.0
    for value in values:
        total = await calc_sum(mcp_url, total, value, timeout_seconds)
    return total


def _flight_cost(flight: dict) -> tuple[float, str | None]:
    if flight.get("status") != "SUCCESS":
        return 0.0, "flight cost unavailable (flight-agent did not return SUCCESS)"
    # Defensive against a malformed/un-validated specialist payload
    # (§31 degrade, never crash): skip options missing a usable price
    # instead of letting a KeyError escape and lose the whole budget.
    options = [o for o in flight.get("options", []) if isinstance(o, dict) and isinstance(o.get("price"), (int, float))]
    if not options:
        return 0.0, "flight cost unavailable (no flight options with a price)"
    recommended_id = flight.get("recommended_option_id")
    for option in options:
        if option.get("id") == recommended_id:
            return float(option["price"]), None
    cheapest = min(options, key=lambda o: o["price"])
    return float(cheapest["price"]), None


def _hotel_cost(hotel: dict, nights: int) -> tuple[float, str | None]:
    if hotel.get("status") != "SUCCESS":
        return 0.0, "hotel cost unavailable (hotel-agent did not return SUCCESS)"
    # Same defensive filtering as _flight_cost: don't let a malformed
    # option (missing/non-numeric price_per_night) raise a KeyError and
    # lose the whole budget.
    options = [
        o for o in hotel.get("options", []) if isinstance(o, dict) and isinstance(o.get("price_per_night"), (int, float))
    ]
    if not options:
        return 0.0, "hotel cost unavailable (no hotel options with a price)"
    # hotel-agent already ranks its own options (rating desc, price asc
    # tiebreak — see hotel-langgraph/src/nodes/rank.ts) and options[0] is
    # the one it recommends. Pricing off the cheapest option instead would
    # silently disagree with "the hotel the response actually shows
    # first", the same way flight_cost above honours
    # `recommended_option_id` rather than re-picking the cheapest flight.
    recommended = options[0]
    return float(recommended["price_per_night"]) * max(nights, 1), None


def _activity_cost_items(activities: dict, travelers: int) -> tuple[list[float], str | None]:
    if activities.get("status") != "SUCCESS":
        return [], "activity cost unavailable (activity-agent did not return SUCCESS)"
    costs: list[float] = []
    for day in activities.get("days", []):
        for item in day.get("items", []):
            # Per-item costs (museum tickets, food tours, etc.) are
            # per-person, same as food_estimate/transport_estimate below —
            # without this, activity_cost would silently undercount for
            # any party bigger than one traveler.
            costs.append(_ACTIVITY_COST_TABLE.get(item.get("category", ""), _DEFAULT_ACTIVITY_ITEM_COST) * travelers)
    if not costs:
        return [], "activity cost unavailable (no activity items)"
    return costs, None


def _budget_status(total: float | None, limit: float | None) -> str:
    if limit is None or total is None:
        return "UNKNOWN"
    if limit <= 0:
        # A stated (even if zero/negative) limit is a real constraint, not
        # "no limit given" — any positive spend against it is by
        # definition over budget. UNKNOWN is reserved for limit is None.
        return "OVER_BUDGET" if total > 0 else "WITHIN_BUDGET"
    ratio = total / limit
    if ratio <= 0.8:
        return "WITHIN_BUDGET"
    if ratio <= 1.0:
        return "NEAR_LIMIT"
    return "OVER_BUDGET"


async def _build_deterministic(req: dict) -> dict:
    currency = req.get("currency") or "BRL"
    try:
        # Defensive coercion (§31 degrade, never crash): a malformed
        # travelers/nights/budget_limit from an upstream caller used to
        # raise an uncaught ValueError/TypeError here, losing the whole
        # budget result instead of degrading to UNAVAILABLE like every
        # other failure mode in this module.
        travelers = max(int(req.get("travelers", 1)), 1)
        nights = max(int(req.get("nights", 1)), 1)
        raw_limit = req.get("budget_limit")
        limit = float(raw_limit) if raw_limit is not None else None
    except (TypeError, ValueError) as exc:
        logger.warning("malformed budget request fields: %s", exc)
        return {
            "status": "UNAVAILABLE",
            "budget_status": "UNKNOWN",
            "total": 0,
            "limit": 0,
            "remaining": 0,
            "notes": f"malformed request: {exc}",
        }

    flight_cost_brl, flight_note = _flight_cost(req.get("flight", {}))
    hotel_cost_brl, hotel_note = _hotel_cost(req.get("hotel", {}), nights)
    activity_items_brl, activity_note = _activity_cost_items(req.get("activities", {}), travelers)

    notes = [n for n in (flight_note, hotel_note, activity_note) if n]

    try:
        with tracer.start_as_current_span("mcp.calculate_budget"):
            activity_cost_brl = await _calc_sum_all(
                settings.mcp_calculator_url, activity_items_brl, settings.request_timeout_seconds
            )
            food_estimate_brl = await calc_multiply(
                settings.mcp_calculator_url,
                settings.food_per_traveler_per_night,
                float(travelers * nights),
                settings.request_timeout_seconds,
            )
            transport_estimate_brl = await calc_multiply(
                settings.mcp_calculator_url,
                settings.transport_per_traveler_per_night,
                float(travelers * nights),
                settings.request_timeout_seconds,
            )
            total_brl = await _calc_sum_all(
                settings.mcp_calculator_url,
                [flight_cost_brl, hotel_cost_brl, activity_cost_brl, food_estimate_brl, transport_estimate_brl],
                settings.request_timeout_seconds,
            )

            with tracer.start_as_current_span("mcp.convert_currency"):
                flight_cost = await convert_currency(
                    settings.mcp_currency_url, amount=flight_cost_brl, from_currency="BRL", to_currency=currency,
                    timeout_seconds=settings.request_timeout_seconds,
                )
                hotel_cost = await convert_currency(
                    settings.mcp_currency_url, amount=hotel_cost_brl, from_currency="BRL", to_currency=currency,
                    timeout_seconds=settings.request_timeout_seconds,
                )
                activity_cost = await convert_currency(
                    settings.mcp_currency_url, amount=activity_cost_brl, from_currency="BRL", to_currency=currency,
                    timeout_seconds=settings.request_timeout_seconds,
                )
                food_estimate = await convert_currency(
                    settings.mcp_currency_url, amount=food_estimate_brl, from_currency="BRL", to_currency=currency,
                    timeout_seconds=settings.request_timeout_seconds,
                )
                transport_estimate = await convert_currency(
                    settings.mcp_currency_url, amount=transport_estimate_brl, from_currency="BRL", to_currency=currency,
                    timeout_seconds=settings.request_timeout_seconds,
                )
                total = await convert_currency(
                    settings.mcp_currency_url, amount=total_brl, from_currency="BRL", to_currency=currency,
                    timeout_seconds=settings.request_timeout_seconds,
                )

            remaining = await calc_subtract(
                settings.mcp_calculator_url, float(limit), total, settings.request_timeout_seconds
            ) if limit is not None else None
    except McpToolError as exc:
        logger.warning("MCP currency/calculator unavailable: %s", exc)
        return {
            "status": "UNAVAILABLE",
            "budget_status": "UNKNOWN",
            "total": 0,
            "limit": limit or 0,
            "remaining": 0,
            "notes": f"MCP unavailable: {exc}",
        }

    budget_status = _budget_status(total, limit)
    status = "UNKNOWN" if limit is None else ("PARTIAL" if notes else "SUCCESS")

    return {
        "status": status,
        "budget_status": budget_status,
        "flight_cost": round(flight_cost, 2),
        "hotel_cost": round(hotel_cost, 2),
        "activity_cost": round(activity_cost, 2),
        "food_estimate": round(food_estimate, 2),
        "transport_estimate": round(transport_estimate, 2),
        "total": round(total, 2),
        "limit": limit or 0,
        "remaining": round(remaining, 2) if remaining is not None else 0,
        "notes": "; ".join(notes),
    }


async def _build_via_crewai(req: dict) -> dict:
    """Only reachable when CREWAI_LLM_MODEL is set. Not exercised by this
    milestone's automated tests; see
    docs/adr/ADR-012-budget-agent-crewai-optional.md and
    agents/budget-crewai/README.md.
    """
    from crewai import Agent, Crew, Task  # noqa: PLC0415 — optional heavy import
    from crewai.tools import tool  # noqa: PLC0415

    from .prompts import BUDGET_PROMPT  # noqa: PLC0415

    @tool("convert_currency")
    async def convert_currency_tool(amount: float, from_currency: str, to_currency: str) -> str:
        """Converts an amount between currencies via MCP Currency."""
        value = await convert_currency(
            settings.mcp_currency_url,
            amount=amount,
            from_currency=from_currency,
            to_currency=to_currency,
            timeout_seconds=settings.request_timeout_seconds,
        )
        return json.dumps({"converted_amount": value})

    @tool("calc_sum")
    async def calc_sum_tool(a: float, b: float) -> str:
        """Adds two numbers via MCP Calculator (never local arithmetic, §33)."""
        value = await calc_sum(settings.mcp_calculator_url, a, b, settings.request_timeout_seconds)
        return json.dumps({"result": value})

    @tool("calc_subtract")
    async def calc_subtract_tool(a: float, b: float) -> str:
        """Subtracts b from a via MCP Calculator (never local arithmetic, §33)."""
        value = await calc_subtract(settings.mcp_calculator_url, a, b, settings.request_timeout_seconds)
        return json.dumps({"result": value})

    @tool("calc_multiply")
    async def calc_multiply_tool(a: float, b: float) -> str:
        """Multiplies two numbers via MCP Calculator (never local arithmetic, §33)."""
        value = await calc_multiply(settings.mcp_calculator_url, a, b, settings.request_timeout_seconds)
        return json.dumps({"result": value})

    # BUDGET_PROMPT instructs the LLM to compute the total exclusively via
    # calculator tool calls (§33) — the agent previously only had the
    # currency-conversion tool bound, so any LLM actually following that
    # instruction had no calculator tools to call.
    budget_agent = Agent(
        role="Budget Specialist",
        goal="Calculate the total estimated trip cost and classify it against the traveler's budget.",
        backstory=BUDGET_PROMPT,
        tools=[convert_currency_tool, calc_sum_tool, calc_subtract_tool, calc_multiply_tool],
    )
    task = Task(
        description=json.dumps(req),
        agent=budget_agent,
        expected_output="JSON matching the BudgetResult schema.",
    )
    crew = Crew(agents=[budget_agent], tasks=[task])

    with tracer.start_as_current_span("llm.budget_agent"):
        # crew.kickoff() is a blocking, synchronous call — running it
        # directly inside this async def would block the event loop (and
        # therefore every other in-flight request this agent is serving)
        # for the LLM call's full duration.
        result = await asyncio.to_thread(crew.kickoff)

    return json.loads(str(result))


async def build_budget_result(req: dict) -> dict:
    if settings.crewai_llm_model:
        try:
            return await _build_via_crewai(req)
        except Exception as exc:  # noqa: BLE001 — LLM path must never break the flow
            logger.warning("CrewAI budget calculation failed, falling back to deterministic path: %s", exc)
    return await _build_deterministic(req)


async def handle_message(message: Message) -> Task:
    text = " ".join(p.text for p in message.parts if getattr(p, "kind", None) == "text")
    try:
        req = json.loads(text)
    except Exception as exc:  # noqa: BLE001
        reply = Message(
            role="agent",
            parts=[TextPart(text=f"invalid budget calculation request: {exc}")],
            context_id=message.context_id,
        )
        return Task(
            context_id=message.context_id or "unknown",
            status=TaskStatus(state="failed", message=reply),
            history=[message, reply],
        )

    result = await build_budget_result(req)
    reply = Message(role="agent", parts=[TextPart(text=json.dumps(result))], context_id=message.context_id)
    return Task(
        context_id=message.context_id or "unknown",
        status=TaskStatus(state="completed", message=reply),
        history=[message, reply],
    )
