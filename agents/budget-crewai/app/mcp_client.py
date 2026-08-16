"""Thin MCP client wrapper shared by the Currency and Calculator tools.

Uses the official `mcp` Python SDK (Streamable HTTP transport), per
PROJECT_SPEC.md §6.2/§33 — same pattern as
activity-beeai/app/mcp_client.py. If an MCP server is unreachable,
callers must treat that as UNAVAILABLE — never fabricate a total (§31).

Fase 8 (§27 "Resiliência"): the connect+call_tool round-trip retries on
any failure, with exponential backoff, up to `retry_attempts` extra
tries. Every MCP tool this agent calls (sum/subtract/multiply,
convert_currency) is a pure computation — safe to retry without the
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


async def calc_sum(mcp_url: str, a: float, b: float, timeout_seconds: float = 30.0) -> float:
    raw = await call_mcp_tool(mcp_url, "sum", {"a": a, "b": b}, timeout_seconds)
    return raw["result"]


async def calc_subtract(mcp_url: str, a: float, b: float, timeout_seconds: float = 30.0) -> float:
    raw = await call_mcp_tool(mcp_url, "subtract", {"a": a, "b": b}, timeout_seconds)
    return raw["result"]


async def calc_multiply(mcp_url: str, a: float, b: float, timeout_seconds: float = 30.0) -> float:
    raw = await call_mcp_tool(mcp_url, "multiply", {"a": a, "b": b}, timeout_seconds)
    return raw["result"]


async def convert_currency(
    mcp_url: str, *, amount: float, from_currency: str, to_currency: str, timeout_seconds: float = 30.0
) -> float:
    if from_currency.upper() == to_currency.upper():
        return amount
    raw = await call_mcp_tool(
        mcp_url,
        "convert_currency",
        {"amount": amount, "from_currency": from_currency, "to_currency": to_currency},
        timeout_seconds,
    )
    conversion = raw.get("conversion")
    if not conversion:
        raise McpToolError(f"unsupported currency pair: {from_currency}/{to_currency}")
    return conversion["converted_amount"]
