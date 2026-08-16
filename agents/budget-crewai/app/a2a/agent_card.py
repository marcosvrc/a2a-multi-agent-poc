from __future__ import annotations

from .models import AgentCapabilities, AgentCard, AgentSkill


def build_agent_card(public_url: str) -> AgentCard:
    return AgentCard(
        name="budget-agent",
        description="Calculates the total estimated trip cost and classifies it against the traveler's budget. Only handles budget math — never flights, hotels or activities search.",
        version="0.1.0",
        url=public_url,
        capabilities=AgentCapabilities(streaming=False, push_notifications=False),
        skills=[
            AgentSkill(
                id="calculate_budget",
                name="Calculate Budget",
                description="Combines flight/hotel/activity costs plus food/transport estimates via MCP Calculator (and MCP Currency when needed) into a total, classified as WITHIN_BUDGET/NEAR_LIMIT/OVER_BUDGET/UNKNOWN.",
                tags=["budget", "specialist"],
            ),
            AgentSkill(
                id="optimize_budget",
                name="Optimize Budget",
                description="Optional skill (PROJECT_SPEC.md §5.5): suggests which cost component to trim first when OVER_BUDGET. Declared for API completeness; not implemented in this milestone.",
                tags=["budget", "specialist"],
            ),
        ],
    )
