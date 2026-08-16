"""Activity Agent — business logic (PROJECT_SPEC.md §5.4).

Two execution paths, mirroring the pattern established for flight-agent
(ADR-009) and generalized here for BeeAI:

- Deterministic (default, used whenever BEEAI_CHAT_MODEL is not set):
  calls MCP Places (and, per day, MCP Weather) directly, builds a
  conflict-free daily itinerary, returns up to `settings.max_days` days.
  This is what keeps RNF-03 (no paid API required by default) true while
  still exercising the real MCP protocol end-to-end.
- BeeAI-driven (only when BEEAI_CHAT_MODEL is set): would use BeeAI's
  ReActAgent with MCP Places/Weather wrapped as tools, letting the model
  decide how to sequence the day. See ADR-011: not exercised by this
  milestone's automated tests (no LLM backend available in CI/dev by
  default), and falls back to the deterministic path on any failure.

Never invents places or forecasts (§31): every item returned here traces
back to a `search_places` MCP call, and weather (when present) always
traces back to a `get_weather` MCP call. Per §5.4 ("permitir execução sem
informação meteorológica" / CT-R03), a Weather MCP failure degrades that
day's `weather` field to null and the itinerary continues — it never
degrades the whole ActivityResult.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, time, timedelta

from opentelemetry import trace

from .a2a.models import Message, Task, TaskStatus, TextPart
from .config import settings
from .mcp_client import McpToolError, get_weather, search_places

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

REQUIRED_FIELDS = ("destination", "start_date", "end_date")

# Items per day are scheduled back-to-back starting at _DAY_START, each
# one beginning _BUFFER_MINUTES after the previous item's end — this is
# what actually "evita conflito de horários" (§5.4) regardless of how
# long any given place's `duration_minutes` is (a fixed slot table like
# "09:00"/"14:00" only avoids overlap by accident, for durations short
# enough to fit the gap between slots).
_DAY_START = time(9, 0)
_BUFFER_MINUTES = 30
_ITEMS_PER_DAY = 2


def _date_range(start_date: str, end_date: str, max_days: int) -> list[str]:
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except (TypeError, ValueError):
        # Malformed date strings must degrade like any other bad input
        # (§31) — never let a ValueError escape into an unhandled -32000.
        return []
    if end < start:
        return []
    days: list[str] = []
    current = start
    while current <= end and len(days) < max_days:
        days.append(current.isoformat())
        current += timedelta(days=1)
    return days


def _build_day_items(day_index: int, places: list[dict]) -> list[dict]:
    if not places:
        return []
    items: list[dict] = []
    cursor = datetime.combine(date.today(), _DAY_START)
    for slot_index in range(_ITEMS_PER_DAY):
        place = places[(day_index * _ITEMS_PER_DAY + slot_index) % len(places)]
        duration = place["duration_minutes"]
        items.append(
            {
                "name": place["name"],
                "start_time": cursor.strftime("%H:%M"),
                "duration_minutes": duration,
                "category": place["category"],
            }
        )
        cursor += timedelta(minutes=duration + _BUFFER_MINUTES)
    return items


async def _fetch_weather(destination: str, day: str) -> str | None:
    with tracer.start_as_current_span("mcp.get_weather"):
        try:
            raw = await get_weather(
                settings.mcp_weather_url,
                destination=destination,
                date=day,
                timeout_seconds=settings.request_timeout_seconds,
            )
        except McpToolError as exc:
            logger.warning("MCP weather unavailable for %s: %s", day, exc)
            return None

    forecast = raw.get("forecast")
    if not forecast:
        return None
    condition = forecast.get("condition")
    temperature = forecast.get("temperature_c")
    if condition is None:
        return None
    if temperature is None:
        return condition
    return f"{condition}, {temperature}°C"


async def _build_deterministic(req: dict) -> dict:
    destination = req["destination"]
    preferences = req.get("preferences", [])

    with tracer.start_as_current_span("mcp.search_places"):
        try:
            raw_places = await search_places(
                settings.mcp_places_url,
                destination=destination,
                preferences=preferences,
                limit=10,
                timeout_seconds=settings.request_timeout_seconds,
            )
        except McpToolError as exc:
            logger.warning("MCP places unavailable: %s", exc)
            return {"status": "UNAVAILABLE", "days": [], "notes": f"MCP unavailable: {exc}"}

    places = raw_places.get("places", [])
    if not places:
        return {"status": "UNAVAILABLE", "days": [], "notes": "no places returned by MCP Places"}

    days = _date_range(req["start_date"], req["end_date"], settings.max_days)
    if not days:
        return {"status": "UNAVAILABLE", "days": [], "notes": "invalid or empty date range"}
    truncated = len(days) == settings.max_days and _date_range(
        req["start_date"], req["end_date"], settings.max_days + 1
    ) != days

    result_days = []
    any_weather = False
    for day_index, day in enumerate(days):
        weather = await _fetch_weather(destination, day)
        if weather is not None:
            any_weather = True
        result_days.append(
            {
                "date": day,
                "weather": weather,
                "items": _build_day_items(day_index, places),
            }
        )

    notes_parts = []
    if not any_weather:
        notes_parts.append("weather forecast unavailable for all days; itinerary built without it")
    if truncated:
        notes_parts.append(f"trip longer than {settings.max_days} days; itinerary truncated to the first {settings.max_days}")
    status = "PARTIAL" if truncated else "SUCCESS"
    return {"status": status, "days": result_days, "notes": "; ".join(notes_parts)}


async def _build_via_beeai(req: dict) -> dict:
    """Only reachable when BEEAI_CHAT_MODEL is set. Not exercised by this
    milestone's automated tests; see
    docs/adr/ADR-011-activity-agent-beeai-optional.md and
    agents/activity-beeai/README.md.
    """
    from beeai_framework.agents.react import ReActAgent  # noqa: PLC0415 — optional heavy import
    from beeai_framework.backend.chat import ChatModel  # noqa: PLC0415
    from beeai_framework.memory import UnconstrainedMemory  # noqa: PLC0415
    from beeai_framework.tools.tool import StringToolOutput, Tool  # noqa: PLC0415

    class SearchPlacesTool(Tool):
        name = "search_places"
        description = "Searches points of interest for a destination via MCP Places."

        async def _run(self, destination: str, preferences: list[str] | None = None) -> StringToolOutput:
            raw = await search_places(
                settings.mcp_places_url,
                destination=destination,
                preferences=preferences or [],
                limit=10,
                timeout_seconds=settings.request_timeout_seconds,
            )
            return StringToolOutput(json.dumps(raw))

    class GetWeatherTool(Tool):
        name = "get_weather"
        description = "Returns a forecast summary for a destination and date via MCP Weather."

        async def _run(self, destination: str, date_str: str) -> StringToolOutput:
            raw = await get_weather(
                settings.mcp_weather_url,
                destination=destination,
                date=date_str,
                timeout_seconds=settings.request_timeout_seconds,
            )
            return StringToolOutput(json.dumps(raw))

    chat_model = ChatModel.from_name(settings.beeai_chat_model)
    agent = ReActAgent(llm=chat_model, tools=[SearchPlacesTool(), GetWeatherTool()], memory=UnconstrainedMemory())

    with tracer.start_as_current_span("llm.activity_agent"):
        response = await agent.run(prompt=json.dumps(req))

    return json.loads(response.result.text)


async def build_activity_result(req: dict) -> dict:
    if settings.beeai_chat_model:
        try:
            return await _build_via_beeai(req)
        except Exception as exc:  # noqa: BLE001 — LLM path must never break the flow
            logger.warning("BeeAI activity planning failed, falling back to deterministic path: %s", exc)
    return await _build_deterministic(req)


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
            parts=[TextPart(text=f"invalid activity planning request: {exc}")],
            context_id=message.context_id,
        )
        return Task(
            context_id=message.context_id or "unknown",
            status=TaskStatus(state="failed", message=reply),
            history=[message, reply],
        )

    result = await build_activity_result(req)
    reply = Message(role="agent", parts=[TextPart(text=json.dumps(result))], context_id=message.context_id)
    return Task(
        context_id=message.context_id or "unknown",
        status=TaskStatus(state="completed", message=reply),
        history=[message, reply],
    )
