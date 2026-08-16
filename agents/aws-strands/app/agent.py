"""AWS Enrichment Agent — business logic (PROJECT_SPEC.md §5.6).

OPTIONAL end to end: the Planner only calls this agent at all when
AWS_AGENT_ENABLED=true (see agents/planner-adk/app/agent.py,
`_delegate_enrichment`), and per §11 ("AWS Enrichment indisponível:
Ignorar. Não marcar o fluxo como falha") this agent must never block the
Planner or affect the overall TravelResponse status — enrichment is
explicitly excluded from that calculation.

Reduced responsibility (§5.6): this agent only enriches — weather
commentary and short destination tips. It never approves/rejects a trip,
computes a budget, or picks a flight/hotel.

Two execution paths, mirroring the pattern established for flight-agent
(ADR-009), activity-agent (ADR-011) and budget-agent (ADR-012):

- Deterministic (default, used whenever MODEL_PROVIDER is unset/unknown):
  `weather_summary` comes from a real MCP Weather call — the same tool
  and behavior activity-agent already uses, never invented (§31).
  `destination_tips` come from a small curated table keyed by traveler
  preference tags, plus one destination-templated generic tip — this is
  generic, templated travel advice, not a fabricated specific claim about
  the destination.
- Strands-driven (MODEL_PROVIDER=ollama|bedrock): uses the AWS Strands
  Agents SDK with either a local Ollama model or Amazon Bedrock to
  generate weather commentary and destination tips. See
  docs/adr/ADR-013-enrichment-agent-strands-optional.md: not exercised by
  this milestone's automated tests (no live Ollama/Bedrock in CI/dev by
  default), and falls back to the deterministic path on any failure.
"""
from __future__ import annotations

import asyncio
import json
import logging

from opentelemetry import trace

from .a2a.models import Message, Task, TaskStatus, TextPart
from .config import settings
from .mcp_client import McpToolError, get_weather

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

REQUIRED_FIELDS = ("destination",)

# Short, generic, destination-agnostic-in-substance travel advice keyed by
# the same preference tags flight/hotel/activity requests already carry
# (see contracts/schemas/travel-request.schema.json `preferences`) — not a
# fabricated specific claim about any destination (§31), just templated
# general advice, the same spirit as activity-agent's per-category
# duration table.
_TIP_TABLE = {
    "beach": "Leve protetor solar e chegue cedo para garantir um bom lugar na praia.",
    "gastronomy": "Reserve com antecedência os restaurantes mais concorridos.",
    "outdoor": "Cheque a previsão do tempo diariamente antes de atividades ao ar livre.",
    "nightlife": "Combine transporte de volta com antecedência para sair à noite com segurança.",
    "culture": "Museus e pontos históricos costumam ter desconto em dias específicos da semana.",
    "adventure": "Contrate atividades de aventura com operadoras licenciadas.",
    "shopping": "Compare preços entre os mercados locais antes de comprar.",
    "family": "Verifique se as atividades escolhidas têm opções para todas as idades do grupo.",
}
_GENERIC_TIP_TEMPLATE = "Leve um documento de identificação válido durante toda a estadia em {destination}."
_MAX_TIPS = 3


def _curated_tips(destination: str, preferences: list[str]) -> list[str]:
    tips: list[str] = []
    for preference in preferences:
        tip = _TIP_TABLE.get(preference.lower())
        if tip and tip not in tips:
            tips.append(tip)
        if len(tips) >= _MAX_TIPS:
            break
    if len(tips) < _MAX_TIPS:
        tips.append(_GENERIC_TIP_TEMPLATE.format(destination=destination))
    return tips[:_MAX_TIPS]


async def _fetch_weather_summary(destination: str, date_str: str) -> str | None:
    with tracer.start_as_current_span("mcp.get_weather"):
        try:
            raw = await get_weather(
                settings.mcp_weather_url,
                destination=destination,
                date=date_str,
                timeout_seconds=settings.request_timeout_seconds,
            )
        except McpToolError as exc:
            logger.warning("MCP weather unavailable for %s: %s", date_str, exc)
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
    preferences = req.get("preferences") or []
    start_date = req.get("start_date")

    weather_summary = await _fetch_weather_summary(destination, start_date) if start_date else None
    destination_tips = _curated_tips(destination, preferences)

    if weather_summary is None and not destination_tips:
        # Only reachable if _curated_tips somehow returned nothing, which
        # it never does today (it always appends the generic template) —
        # kept as an explicit degrade path rather than an assumption, per
        # §31 ("nunca fabricar dado").
        return {"status": "UNAVAILABLE", "provider": None, "weather_summary": None, "destination_tips": []}

    return {
        "status": "SUCCESS",
        "provider": "mock",
        "weather_summary": weather_summary,
        "destination_tips": destination_tips,
    }


async def _build_via_strands(req: dict) -> dict:
    """Only reachable when MODEL_PROVIDER is 'ollama' or 'bedrock'. Not
    exercised by this milestone's automated tests; see
    docs/adr/ADR-013-enrichment-agent-strands-optional.md and
    agents/aws-strands/README.md.
    """
    from strands import Agent  # noqa: PLC0415 — optional heavy import

    from .prompts import ENRICHMENT_PROMPT  # noqa: PLC0415

    if settings.model_provider == "bedrock":
        from strands.models import BedrockModel  # noqa: PLC0415

        model = BedrockModel(model_id=settings.bedrock_model_id, region_name=settings.aws_region)
    else:
        from strands.models.ollama import OllamaModel  # noqa: PLC0415

        model = OllamaModel(host=settings.ollama_host, model_id=settings.ollama_model_id)

    destination = req["destination"]
    start_date = req.get("start_date")
    # Weather still comes from MCP, even on the LLM path — the model is
    # only asked to turn a real forecast into commentary/tips, never to
    # invent the forecast itself (§31).
    weather_summary = await _fetch_weather_summary(destination, start_date) if start_date else None

    agent = Agent(model=model, system_prompt=ENRICHMENT_PROMPT)
    prompt = json.dumps(
        {
            "destination": destination,
            "preferences": req.get("preferences") or [],
            "weather_summary": weather_summary,
        }
    )

    with tracer.start_as_current_span("llm.enrichment_agent"):
        # Strands' Agent.__call__ is a blocking, synchronous call — run it
        # off the event loop the same way budget-agent's optional CrewAI
        # path does for crew.kickoff(), so one slow LLM call doesn't stall
        # every other in-flight request this agent is serving.
        response = await asyncio.to_thread(agent, prompt)

    raw = json.loads(str(response))
    return {
        "status": "SUCCESS",
        "provider": settings.model_provider,
        "weather_summary": raw.get("weather_summary", weather_summary),
        "destination_tips": raw.get("destination_tips") or [],
    }


async def build_enrichment_result(req: dict) -> dict:
    if settings.model_provider in ("ollama", "bedrock"):
        try:
            return await _build_via_strands(req)
        except Exception as exc:  # noqa: BLE001 — LLM path must never break the flow
            logger.warning("Strands enrichment failed, falling back to deterministic path: %s", exc)
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
            parts=[TextPart(text=f"invalid enrichment request: {exc}")],
            context_id=message.context_id,
        )
        return Task(
            context_id=message.context_id or "unknown",
            status=TaskStatus(state="failed", message=reply),
            history=[message, reply],
        )

    result = await build_enrichment_result(req)
    reply = Message(role="agent", parts=[TextPart(text=json.dumps(result))], context_id=message.context_id)
    return Task(
        context_id=message.context_id or "unknown",
        status=TaskStatus(state="completed", message=reply),
        history=[message, reply],
    )
