from __future__ import annotations

from .models import AgentCapabilities, AgentCard, AgentSkill


def build_agent_card(public_url: str) -> AgentCard:
    return AgentCard(
        name="aws-enrichment-agent",
        description=(
            "Optional trip enrichment: weather commentary and short destination tips. "
            "Never approves/rejects a trip, computes budget, or picks flights/hotels — "
            "and never blocks the Planner (PROJECT_SPEC.md §5.6)."
        ),
        version="0.1.0",
        url=public_url,
        capabilities=AgentCapabilities(streaming=False, push_notifications=False),
        skills=[
            AgentSkill(
                id="enrich_destination",
                name="Enrich Destination",
                description=(
                    "Adds weather commentary (via MCP Weather) and short destination tips for the trip. "
                    "Entirely optional — the Planner and the overall TravelResponse status work without it."
                ),
                tags=["enrichment", "optional"],
            )
        ],
    )
