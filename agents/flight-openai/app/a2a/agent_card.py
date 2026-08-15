from __future__ import annotations

from .models import AgentCapabilities, AgentCard, AgentSkill


def build_agent_card(public_url: str) -> AgentCard:
    return AgentCard(
        name="flight-agent",
        description="Searches and ranks flight options for a trip. Only handles flights — never hotels, activities or budget.",
        version="0.1.0",
        url=public_url,
        capabilities=AgentCapabilities(streaming=False, push_notifications=False),
        skills=[
            AgentSkill(
                id="search_flights",
                name="Search Flights",
                description="Searches for flights based on origin, destination, dates and traveler count via MCP Flight Search, returns up to 5 ranked options.",
                tags=["flight", "specialist"],
            )
        ],
    )
