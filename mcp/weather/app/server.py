"""MCP Weather server (PROJECT_SPEC.md §33 "MCP Weather").

Exposes a single tool, `get_weather`, over MCP Streamable HTTP (§6.3).
Runs in MOCK_MODE by default (§23/§5.4: "O Weather MCP poderá usar mock
local"), so the POC needs no paid weather API.
"""
from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from .mock_data import get_weather_mock

MOCK_MODE = os.getenv("MOCK_MODE", "true").lower() == "true"

mcp = FastMCP(
    name="mcp-weather",
    host="0.0.0.0",
    port=int(os.getenv("PORT", "9004")),
    stateless_http=True,
)


@mcp.tool(
    name="get_weather",
    description="Returns a forecast summary for a destination and date.",
)
def get_weather(destination: str, date: str) -> dict:
    """In MOCK_MODE (default) results are deterministic (same input ->
    same output), per PROJECT_SPEC.md §23/§31. Callers must treat any
    failure as "no forecast available" and continue without weather
    (§5.4: "permitir execução sem informação meteorológica"), never block
    the itinerary on this tool.
    """
    if not MOCK_MODE:
        return {
            "provider": "unavailable",
            "forecast": None,
            "notes": "MOCK_MODE=false and no real weather provider is configured in this milestone.",
        }

    forecast = get_weather_mock(destination, date)
    return {"provider": "mock", "forecast": forecast}


@mcp.custom_route("/health", methods=["GET"])
async def health(_request: Request) -> JSONResponse:
    return JSONResponse({"status": "UP"})


@mcp.custom_route("/ready", methods=["GET"])
async def ready(_request: Request) -> JSONResponse:
    return JSONResponse({"status": "READY", "dependencies": {"mock_mode": MOCK_MODE}})


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
