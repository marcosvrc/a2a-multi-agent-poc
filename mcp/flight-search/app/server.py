"""MCP Flight Search server (PROJECT_SPEC.md §33 "MCP Flight").

Exposes a single tool, `search_flights`, over MCP Streamable HTTP
(§6.3). Runs in MOCK_MODE by default (§23) so the POC needs no paid
flight-search API. When MOCK_MODE=false, a real provider integration
would be plugged in here (not implemented in this milestone — no data
source was specified, and PROJECT_SPEC.md §31 forbids inventing prices).
"""
from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from .mock_data import search_flights_mock

MOCK_MODE = os.getenv("MOCK_MODE", "true").lower() == "true"

mcp = FastMCP(
    name="mcp-flight-search",
    host="0.0.0.0",
    port=int(os.getenv("PORT", "9001")),
    stateless_http=True,
)


@mcp.tool(
    name="search_flights",
    description="Searches for flights between origin and destination for the given dates and traveler count.",
)
def search_flights(
    origin: str,
    destination: str,
    start_date: str,
    end_date: str,
    travelers: int = 1,
) -> dict:
    """Returns up to 5 flight options. In MOCK_MODE (default) results are
    deterministic (same input -> same output), per PROJECT_SPEC.md §23/§31.
    """
    if not MOCK_MODE:
        return {
            "provider": "unavailable",
            "flights": [],
            "notes": "MOCK_MODE=false and no real flight provider is configured in this milestone.",
        }

    flights = search_flights_mock(origin, destination, start_date, end_date, travelers)
    return {"provider": "mock", "flights": flights}


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
