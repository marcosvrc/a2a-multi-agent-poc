"""Minimal A2A protocol data model.

This POC implements a lightweight, spec-compliant HTTP adapter for the A2A
protocol (Agent Card, Message/Parts, Task, JSON-RPC 2.0 methods
`message/send` and `tasks/get`) instead of pinning to a specific version of
the official `a2a-sdk`, per PROJECT_SPEC.md §42 rule 7 ("Se um SDK não
fornecer A2A nativamente, implemente um adapter compatível"). See
docs/adr/ADR-008-custom-a2a-adapter.md for the rationale.

Reference: https://a2a-protocol.org/latest/topics/key-concepts/
"""
from __future__ import annotations

import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

TaskState = Literal[
    "submitted",
    "working",
    "input-required",
    "completed",
    "failed",
    "canceled",
]


class TextPart(BaseModel):
    kind: Literal["text"] = "text"
    text: str


class DataPart(BaseModel):
    kind: Literal["data"] = "data"
    data: dict[str, Any]


Part = TextPart | DataPart


class Message(BaseModel):
    role: Literal["user", "agent"]
    parts: list[Part]
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    context_id: str | None = None
    task_id: str | None = None


class TaskStatus(BaseModel):
    state: TaskState
    message: Message | None = None
    timestamp: float = Field(default_factory=time.time)


class Artifact(BaseModel):
    artifact_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    parts: list[Part]


class Task(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    context_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: TaskStatus
    artifacts: list[Artifact] = Field(default_factory=list)
    history: list[Message] = Field(default_factory=list)


class AgentSkill(BaseModel):
    id: str
    name: str
    description: str
    tags: list[str] = Field(default_factory=list)


class AgentCapabilities(BaseModel):
    streaming: bool = False
    push_notifications: bool = False


class AgentCard(BaseModel):
    name: str
    description: str
    version: str
    url: str
    protocol_version: str = "0.3"
    capabilities: AgentCapabilities = Field(default_factory=AgentCapabilities)
    skills: list[AgentSkill] = Field(default_factory=list)
    default_input_modes: list[str] = Field(default_factory=lambda: ["text/plain", "application/json"])
    default_output_modes: list[str] = Field(default_factory=lambda: ["text/plain", "application/json"])
