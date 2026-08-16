"""Thin MCP client wrapper for MCP Weather — same pattern as
activity-beeai/app/mcp_client.py and flight-openai/app/mcp_client.py.
If MCP Weather is unreachable, callers must treat that as "no forecast
available" — never fabricate weather data (§31).

Fase 8 (§27 "Resiliência"): the connect+call_tool round-trip retries on
any failure, with exponential backoff, up to `retry_attempts` extra
tries — get_weather is a pure read, safe to retry without the
non-idempotent-call caveat that applies to A2A `message/send` (see
planner-adk/app/a2a/client.py for that side of §27).
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import timedelta

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

logger = logging.getLogger(__name__)


class McpToolError(Exception):
    pass


async def _with_retry(fn, *, retry_attempts: int, retry_backoff_base_seconds: float):
    last_exc: Exception | None = None
    for attempt in range(retry_attempts + 1):
        try:
            return await fn()
        except Exception as exc:  # noqa: BLE001 — any failure here is retry-eligible
            last_exc = exc
            if attempt >= retry_attempts:
                break
            delay = retry_backoff_base_seconds * (2**attempt)
            logger.warning(
                "MCP call failed (attempt %d/%d): %s — retrying in %.2fs",
                attempt + 1,
                retry_attempts + 1,
                exc,
                delay,
            )
            await asyncio.sleep(delay)
    assert last_exc is not None
    raise last_exc


async def call_mcp_tool(
    mcp_url: str,
    tool_name: str,
    arguments: dict,
    timeout_seconds: float = 30.0,
    retry_attempts: int = 2,
    retry_backoff_base_seconds: float = 0.5,
) -> dict:
    async def _attempt():
        # `timeout` alone only bounds the initial HTTP request — the SDK's
        # default `sse_read_timeout` is 300s regardless, and ClientSession
        # has no deadline unless `read_timeout_seconds` is passed to
        # call_tool. Without both, the configured timeout is not actually
        # enforced on a slow/hung MCP server.
        async with streamablehttp_client(
            mcp_url, timeout=timeout_seconds, sse_read_timeout=timeout_seconds
        ) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await session.call_tool(
                    tool_name, arguments, read_timeout_seconds=timedelta(seconds=timeout_seconds)
                )

    try:
        result = await _with_retry(
            _attempt, retry_attempts=retry_attempts, retry_backoff_base_seconds=retry_backoff_base_seconds
        )
    except Exception as exc:  # noqa: BLE001 — MCP unreachable must degrade, not crash
        raise McpToolError(str(exc)) from exc

    if result.isError:
        raise McpToolError(f"MCP tool '{tool_name}' returned an error: {result.content}")

    if result.structuredContent:
        return result.structuredContent

    for block in result.content:
        if getattr(block, "type", None) == "text":
            return json.loads(block.text)

    raise McpToolError(f"MCP tool '{tool_name}' returned no parseable content")


async def get_weather(mcp_url: str, *, destination: str, date: str, timeout_seconds: float = 30.0) -> dict:
    return await call_mcp_tool(mcp_url, "get_weather", {"destination": destination, "date": date}, timeout_seconds)
