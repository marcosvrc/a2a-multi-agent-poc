"""Thin MCP client wrapper for the Flight Search tool.

Uses the official `mcp` Python SDK (Streamable HTTP transport), per
PROJECT_SPEC.md §6.2/§33. If the MCP server is unreachable, callers must
treat that as UNAVAILABLE — never fabricate flight data (§31).
"""
from __future__ import annotations

import json
import logging

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

logger = logging.getLogger(__name__)


class McpFlightSearchError(Exception):
    pass


async def search_flights(
    mcp_url: str,
    *,
    origin: str,
    destination: str,
    start_date: str,
    end_date: str,
    travelers: int,
    timeout_seconds: float = 30.0,
) -> dict:
    try:
        async with streamablehttp_client(mcp_url, timeout=timeout_seconds) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(
                    "search_flights",
                    {
                        "origin": origin,
                        "destination": destination,
                        "start_date": start_date,
                        "end_date": end_date,
                        "travelers": travelers,
                    },
                )
    except Exception as exc:  # noqa: BLE001 — MCP unreachable must degrade, not crash
        raise McpFlightSearchError(str(exc)) from exc

    if result.isError:
        raise McpFlightSearchError(f"MCP tool returned an error: {result.content}")

    if result.structuredContent:
        return result.structuredContent

    for block in result.content:
        if getattr(block, "type", None) == "text":
            return json.loads(block.text)

    raise McpFlightSearchError("MCP tool returned no parseable content")
