from __future__ import annotations

from .models import AgentCapabilities, AgentCard, AgentSkill


def build_agent_card(public_url: str) -> AgentCard:
    return AgentCard(
        name="mock-specialist-agent",
        description="Trivial A2A specialist used to validate agent discovery and delegation end-to-end (M1 foundation).",
        version="0.1.0",
        url=public_url,
        capabilities=AgentCapabilities(streaming=False, push_notifications=False),
        skills=[
            AgentSkill(
                id="echo_ping",
                name="Echo Ping",
                description="Echoes back the received text to prove A2A message/send round-trips correctly.",
                tags=["mock", "m1-foundation"],
            )
        ],
    )
