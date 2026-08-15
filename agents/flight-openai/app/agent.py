"""Flight Agent — business logic (PROJECT_SPEC.md §5.2).

Two execution paths:

- Deterministic (default, used whenever OPENAI_API_KEY is not set): calls
  MCP Flight Search directly, ranks by price, returns up to 5 options.
  This is what keeps RNF-03 (no paid API required by default) true while
  still exercising the real MCP protocol end-to-end.
- LLM-driven (only when OPENAI_API_KEY is set): uses the OpenAI Agents
  SDK (`agents` package) with the prompt in `prompts.py` and the MCP
  search wrapped as a function tool, letting the model decide how to call
  it and format the final FlightResult. Falls back to the deterministic
  path if the LLM call fails, so a flaky LLM never breaks the flow.

Never invents flight data (§31): every option returned here traces back
to a `search_flights` MCP call.
"""
from __future__ import annotations

import json
import logging

from opentelemetry import trace

from .a2a.models import Message, Task, TaskStatus, TextPart
from .config import settings
from .mcp_client import McpFlightSearchError
from .mcp_client import search_flights as mcp_search_flights
from .prompts import FLIGHT_PROMPT

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

REQUIRED_FIELDS = ("origin", "destination", "start_date", "end_date")


def _rank_and_trim(flights: list[dict]) -> tuple[list[dict], str | None]:
    ranked = sorted(flights, key=lambda f: f["price"])[:5]
    recommended_id = ranked[0]["id"] if ranked else None
    return ranked, recommended_id


async def _search_deterministic(req: dict) -> dict:
    with tracer.start_as_current_span("mcp.flight_search"):
        try:
            raw = await mcp_search_flights(
                settings.mcp_flight_url,
                origin=req["origin"],
                destination=req["destination"],
                start_date=req["start_date"],
                end_date=req["end_date"],
                travelers=int(req.get("travelers", 1)),
                timeout_seconds=settings.request_timeout_seconds,
            )
        except McpFlightSearchError as exc:
            logger.warning("MCP flight search unavailable: %s", exc)
            return {"status": "UNAVAILABLE", "options": [], "notes": f"MCP unavailable: {exc}"}

    flights = raw.get("flights", [])
    ranked, recommended_id = _rank_and_trim(flights)
    options = [
        {
            "id": f["id"],
            "origin": f["origin"],
            "destination": f["destination"],
            "price": f["price"],
            "currency": f["currency"],
            "provider": f.get("provider", "mock"),
        }
        for f in ranked
    ]
    status = "SUCCESS" if options else "UNAVAILABLE"
    result: dict = {"status": status, "options": options, "notes": raw.get("notes", "")}
    if recommended_id:
        result["recommended_option_id"] = recommended_id
    return result


async def _search_via_llm(req: dict) -> dict:
    """Only reachable when OPENAI_API_KEY is set. Not exercised by this
    milestone's automated tests (no key available in CI/dev by default);
    see agents/flight-openai/README.md.
    """
    from agents import Agent, Runner, function_tool

    @function_tool
    async def search_flights_tool(
        origin: str, destination: str, start_date: str, end_date: str, travelers: int
    ) -> str:
        """Search flights via the MCP Flight Search server. Returns raw JSON."""
        try:
            raw = await mcp_search_flights(
                settings.mcp_flight_url,
                origin=origin,
                destination=destination,
                start_date=start_date,
                end_date=end_date,
                travelers=travelers,
                timeout_seconds=settings.request_timeout_seconds,
            )
        except McpFlightSearchError as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(raw)

    agent = Agent(name="flight-agent", instructions=FLIGHT_PROMPT, tools=[search_flights_tool])

    with tracer.start_as_current_span("llm.flight_agent"):
        result = await Runner.run(agent, json.dumps(req))

    return json.loads(result.final_output)


async def build_flight_result(req: dict) -> dict:
    if settings.openai_api_key:
        try:
            return await _search_via_llm(req)
        except Exception as exc:  # noqa: BLE001 — LLM path must never break the flow
            logger.warning("LLM flight search failed, falling back to deterministic path: %s", exc)
    return await _search_deterministic(req)


async def handle_message(message: Message) -> Task:
    text = " ".join(p.text for p in message.parts if getattr(p, "kind", None) == "text")
    try:
        req = json.loads(text)
        missing = [f for f in REQUIRED_FIELDS if f not in req]
        if missing:
            raise ValueError(f"missing fields: {missing}")
    except Exception as exc:  # noqa: BLE001
        reply = Message(
            role="agent",
            parts=[TextPart(text=f"invalid flight search request: {exc}")],
            context_id=message.context_id,
        )
        return Task(
            context_id=message.context_id or "unknown",
            status=TaskStatus(state="failed", message=reply),
            history=[message, reply],
        )

    result = await build_flight_result(req)
    reply = Message(role="agent", parts=[TextPart(text=json.dumps(result))], context_id=message.context_id)
    return Task(
        context_id=message.context_id or "unknown",
        status=TaskStatus(state="completed", message=reply),
        history=[message, reply],
    )
