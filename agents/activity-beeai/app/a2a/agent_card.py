from __future__ import annotations

from .models import AgentCapabilities, AgentCard, AgentSkill


def build_agent_card(public_url: str) -> AgentCard:
    return AgentCard(
        name="activity-agent",
        description="Builds a daily activity itinerary for a trip. Only handles activities — never flights, hotels or budget.",
        version="0.1.0",
        url=public_url,
        capabilities=AgentCapabilities(streaming=False, push_notifications=False),
        skills=[
            AgentSkill(
                id="plan_activities",
                name="Plan Activities",
                description="Builds a day-by-day itinerary for the trip dates using MCP Places and, when available, MCP Weather.",
                tags=["activity", "specialist"],
            ),
            AgentSkill(
                id="optimize_itinerary",
                name="Optimize Itinerary",
                description="Re-ranks/deduplicates an existing itinerary to avoid schedule conflicts and better match preferences.",
                tags=["activity", "specialist"],
            ),
        ],
    )
