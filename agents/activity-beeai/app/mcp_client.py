"""Thin MCP client wrapper shared by the Places and Weather tools.

Uses the official `mcp` Python SDK (Streamable HTTP transport), per
PROJECT_SPEC.md §6.2/§33 — same pattern as flight-openai/app/mcp_client.py
and hotel-langgraph/src/mcpClient.ts. If an MCP server is unreachable,
callers must treat that as UNAVAILABLE/missing — never fabricate data
(§31).
"""
from __future__ import annotations

import json
import logging

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

logger = logging.getLogger(__name__)


class McpToolError(Exception):
    pass


async def call_mcp_tool(mcp_url: str, tool_name: str, arguments: dict, timeout_seconds: float = 30.0) -> dict:
    try:
        async with streamablehttp_client(mcp_url, timeout=timeout_seconds) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
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


async def search_places(mcp_url: str, *, destination: str, preferences: list[str], limit: int = 10, timeout_seconds: float = 30.0) -> dict:
    return await call_mcp_tool(
        mcp_url,
        "search_places",
        {"destination": destination, "preferences": preferences, "limit": limit},
        timeout_seconds,
    )


async def get_weather(mcp_url: str, *, destination: str, date: str, timeout_seconds: float = 30.0) -> dict:
    return await call_mcp_tool(mcp_url, "get_weather", {"destination": destination, "date": date}, timeout_seconds)
