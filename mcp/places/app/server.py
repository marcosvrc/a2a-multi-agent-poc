"""MCP Places server (PROJECT_SPEC.md §33 "MCP Places").

Exposes a single tool, `search_places`, over MCP Streamable HTTP (§6.3).
Runs in MOCK_MODE by default (§23) so the POC needs no paid places API.
"""
from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from .mock_data import search_places_mock

MOCK_MODE = os.getenv("MOCK_MODE", "true").lower() == "true"

mcp = FastMCP(
    name="mcp-places",
    host="0.0.0.0",
    port=int(os.getenv("PORT", "9003")),
    stateless_http=True,
)


@mcp.tool(
    name="search_places",
    description="Searches points of interest for a destination, optionally filtered/prioritized by preference categories.",
)
def search_places(destination: str, preferences: list[str] | None = None, limit: int = 10) -> dict:
    """Returns up to `limit` places. In MOCK_MODE (default) results are
    deterministic (same input -> same output), per PROJECT_SPEC.md §23/§31.
    """
    if not MOCK_MODE:
        return {
            "provider": "unavailable",
            "places": [],
            "notes": "MOCK_MODE=false and no real places provider is configured in this milestone.",
        }

    places = search_places_mock(destination, preferences or [], limit)
    return {"provider": "mock", "places": places}


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
