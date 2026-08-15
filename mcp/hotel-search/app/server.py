"""MCP Hotel Search server (PROJECT_SPEC.md §33 "MCP Hotel").

Exposes a single tool, `search_hotels`, over MCP Streamable HTTP (§6.3).
Runs in MOCK_MODE by default (§23) — no paid hotel-search API required.
"""
from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from .mock_data import search_hotels_mock

MOCK_MODE = os.getenv("MOCK_MODE", "true").lower() == "true"

mcp = FastMCP(
    name="mcp-hotel-search",
    host="0.0.0.0",
    port=int(os.getenv("PORT", "9002")),
    stateless_http=True,
)


@mcp.tool(
    name="search_hotels",
    description="Searches for hotels at a destination for the given dates and guest count.",
)
def search_hotels(
    destination: str,
    start_date: str,
    end_date: str,
    guests: int = 1,
) -> dict:
    """Returns hotel options. In MOCK_MODE (default) results are
    deterministic (same input -> same output), per PROJECT_SPEC.md §23/§31.
    """
    if not MOCK_MODE:
        return {
            "provider": "unavailable",
            "hotels": [],
            "notes": "MOCK_MODE=false and no real hotel provider is configured in this milestone.",
        }

    hotels = search_hotels_mock(destination, start_date, end_date, guests)
    return {"provider": "mock", "hotels": hotels}


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
