"""Mock Specialist Agent — business logic.

Purpose (PROJECT_SPEC.md §43 Fase 1 / §51 Milestone M1): a trivial A2A
server used to validate agent-to-agent communication end-to-end (Agent
Card, Message/Parts, Task, JSON-RPC) *before* any real specialist
(Flight/Hotel/Activity/Budget/Enrichment) is implemented.

Skill: `echo_ping` — echoes the received text back with a deterministic
acknowledgement, so contract/E2E tests have something stable to assert on.
"""
from __future__ import annotations

import logging

from .a2a.models import Message, Task, TaskStatus, TextPart

logger = logging.getLogger(__name__)


async def handle_message(message: Message) -> Task:
    text_parts = [p.text for p in message.parts if getattr(p, "kind", None) == "text"]
    incoming_text = " ".join(text_parts) if text_parts else ""

    logger.info(
        "mock agent received message",
        extra={"event": "agent_call_received", "correlation_id": message.context_id},
    )

    reply_text = f"mock-specialist-agent received: {incoming_text!r}"

    reply = Message(role="agent", parts=[TextPart(text=reply_text)], context_id=message.context_id)
    return Task(
        context_id=message.context_id or "unknown",
        status=TaskStatus(state="completed", message=reply),
        history=[message, reply],
    )
