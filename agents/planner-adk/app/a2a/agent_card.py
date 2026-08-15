from __future__ import annotations

from .models import AgentCapabilities, AgentCard, AgentSkill


def build_agent_card(public_url: str) -> AgentCard:
    return AgentCard(
        name="planner-agent",
        description="Orchestrates the multi-agent travel planning flow: discovers specialists via the Agent Registry and delegates work over A2A. Never executes flight/hotel/activity/weather logic itself.",
        version="0.1.0",
        url=public_url,
        capabilities=AgentCapabilities(streaming=False, push_notifications=False),
        skills=[
            AgentSkill(
                id="plan_trip",
                name="Plan Trip",
                description="Receives a TravelRequest, discovers specialist agents, delegates in parallel, and consolidates a TravelResponse.",
                tags=["planner", "orchestration"],
            )
        ],
    )
