"""MCP Currency server (PROJECT_SPEC.md §33 "MCP Currency").

Exposes a single tool, `convert_currency`, over MCP Streamable HTTP
(§6.3). Runs in MOCK_MODE by default (§23) so the POC needs no paid
exchange-rate API.
"""
from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from .mock_data import convert_currency_mock

MOCK_MODE = os.getenv("MOCK_MODE", "true").lower() == "true"

mcp = FastMCP(
    name="mcp-currency",
    host="0.0.0.0",
    port=int(os.getenv("PORT", "9005")),
    stateless_http=True,
)


@mcp.tool(
    name="convert_currency",
    description="Converts an amount from one currency to another using a fixed illustrative exchange rate table.",
)
def convert_currency(amount: float, from_currency: str, to_currency: str) -> dict:
    """In MOCK_MODE (default) results are deterministic (same input ->
    same output), per PROJECT_SPEC.md §23/§31.
    """
    if not MOCK_MODE:
        return {
            "provider": "unavailable",
            "conversion": None,
            "notes": "MOCK_MODE=false and no real currency provider is configured in this milestone.",
        }

    conversion = convert_currency_mock(amount, from_currency, to_currency)
    if conversion is None:
        return {"provider": "mock", "conversion": None, "notes": f"unsupported currency pair: {from_currency}/{to_currency}"}
    return {"provider": "mock", "conversion": conversion}


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
