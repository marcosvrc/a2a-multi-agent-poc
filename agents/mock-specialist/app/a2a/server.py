"""FastAPI wiring for the A2A adapter: agent-card route + JSON-RPC 2.0 route.

Supported JSON-RPC methods (subset required for M1, per PROJECT_SPEC.md §6.1
and §6.4):
  - message/send
  - tasks/get
  - tasks/cancel (best-effort; most POC tasks complete synchronously)

Streaming (`message/stream`, SSE) is not implemented in M1. The spec allows
this: "O sistema deverá funcionar também sem streaming." (§6.5)

Fase 9 (§7/§56 "M6 Security"): `build_jsonrpc_router` takes an optional
`require_auth` callable, invoked before any JSON-RPC method is
dispatched. It raises `fastapi.HTTPException(401)` on an unauthorized
request — FastAPI turns that into a proper 401 response on its own, no
extra handling needed here. `None` (the default) means "no auth check",
used by tests and by any deployment explicitly running `AUTH_MODE=none`.
The Agent Card route is never gated — see app/auth.py's module docstring
for why.
"""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .models import AgentCard, Message, Task, TaskStatus

logger = logging.getLogger(__name__)

TaskHandler = Callable[[Message], Awaitable[Task]]


class InMemoryTaskStore:
    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}

    def save(self, task: Task) -> None:
        self._tasks[task.id] = task

    def get(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)


def _jsonrpc_error(request_id: Any, code: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content={
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        },
    )


def _jsonrpc_result(request_id: Any, result: dict[str, Any]) -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content={"jsonrpc": "2.0", "id": request_id, "result": result},
    )


def build_agent_card_router(card: AgentCard) -> APIRouter:
    router = APIRouter()

    @router.get("/.well-known/agent-card.json")
    async def get_agent_card() -> dict[str, Any]:
        return card.model_dump(mode="json", by_alias=True)

    return router


def build_jsonrpc_router(
    handler: TaskHandler,
    task_store: InMemoryTaskStore,
    require_auth: Callable[[Request], Any] | None = None,
) -> APIRouter:
    """Builds the JSON-RPC 2.0 endpoint implementing the A2A methods.

    `handler` receives the incoming user Message and must return a completed
    (or failed) Task. The router takes care of the JSON-RPC envelope,
    task persistence and `tasks/get` / `tasks/cancel` lookups.

    `require_auth` (Fase 9, §7/§56): if provided, called with the raw
    `Request` before anything else — see app/auth.py::verify_request, the
    usual value passed here.
    """
    router = APIRouter()

    @router.post("/a2a")
    async def jsonrpc_endpoint(request: Request) -> JSONResponse:
        if require_auth is not None:
            require_auth(request)

        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            return _jsonrpc_error(None, -32700, "Parse error: invalid JSON")

        if not isinstance(body, dict):
            # Valid JSON (e.g. `[]`, `"x"`, `3`) but not a JSON-RPC object —
            # without this guard body.get(...) below raises AttributeError,
            # turning a malformed-but-parseable request into an unhandled
            # 500 instead of a proper JSON-RPC error envelope.
            return _jsonrpc_error(None, -32600, "Invalid Request: body must be a JSON object")

        request_id = body.get("id")
        method = body.get("method")
        params = body.get("params") or {}

        if method == "message/send":
            try:
                message = Message.model_validate(params.get("message"))
            except Exception as exc:  # noqa: BLE001
                return _jsonrpc_error(request_id, -32602, f"Invalid params: {exc}")

            try:
                task = await handler(message)
            except Exception as exc:  # noqa: BLE001
                logger.exception("agent handler failed")
                return _jsonrpc_error(request_id, -32000, f"Agent execution error: {exc}")

            task_store.save(task)
            return _jsonrpc_result(request_id, task.model_dump(mode="json"))

        if method == "tasks/get":
            task_id = params.get("id")
            task = task_store.get(task_id) if task_id else None
            if task is None:
                return _jsonrpc_error(request_id, -32001, f"Task '{task_id}' not found")
            return _jsonrpc_result(request_id, task.model_dump(mode="json"))

        if method == "tasks/cancel":
            task_id = params.get("id")
            task = task_store.get(task_id) if task_id else None
            if task is None:
                return _jsonrpc_error(request_id, -32001, f"Task '{task_id}' not found")
            task.status = TaskStatus(state="canceled")
            task_store.save(task)
            return _jsonrpc_result(request_id, task.model_dump(mode="json"))

        return _jsonrpc_error(request_id, -32601, f"Method '{method}' not found")

    return router
