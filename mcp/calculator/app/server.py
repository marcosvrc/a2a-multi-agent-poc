"""MCP Calculator server (PROJECT_SPEC.md §33 "MCP Calculator").

Exposes four tools — `sum`, `subtract`, `multiply`, `divide` — over MCP
Streamable HTTP (§6.3). Each tool performs exactly one fixed binary
arithmetic operation; there is no expression-evaluation tool, and no
`eval`/`exec` is used anywhere in this server, per the explicit spec
constraint: "Não permitir expressão arbitrária executada via eval."
"""
from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

mcp = FastMCP(
    name="mcp-calculator",
    host="0.0.0.0",
    port=int(os.getenv("PORT", "9006")),
    stateless_http=True,
)


@mcp.tool(name="sum", description="Adds two numbers: a + b.")
def sum_tool(a: float, b: float) -> dict:
    return {"result": a + b}


@mcp.tool(name="subtract", description="Subtracts two numbers: a - b.")
def subtract_tool(a: float, b: float) -> dict:
    return {"result": a - b}


@mcp.tool(name="multiply", description="Multiplies two numbers: a * b.")
def multiply_tool(a: float, b: float) -> dict:
    return {"result": a * b}


@mcp.tool(name="divide", description="Divides two numbers: a / b. Returns an error for b == 0 instead of raising.")
def divide_tool(a: float, b: float) -> dict:
    if b == 0:
        return {"result": None, "error": "division by zero"}
    return {"result": a / b}


@mcp.custom_route("/health", methods=["GET"])
async def health(_request: Request) -> JSONResponse:
    return JSONResponse({"status": "UP"})


@mcp.custom_route("/ready", methods=["GET"])
async def ready(_request: Request) -> JSONResponse:
    return JSONResponse({"status": "READY", "dependencies": {}})


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
