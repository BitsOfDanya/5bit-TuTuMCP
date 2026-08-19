from __future__ import annotations

from time import perf_counter

from fastapi import APIRouter, HTTPException

from app.tutu.client import TutuMCPClient


router = APIRouter(
    prefix="/api/v1/system",
    tags=["system"],
)


@router.get("/mcp")
async def mcp_status() -> dict:
    """
    Smoke-test for the real Tutu MCP connection.

    This endpoint is useful for:
    - deployment verification;
    - hackathon demo;
    - proving that the backend actually talks to Tutu MCP.

    It does not perform a trip search.
    """

    client = TutuMCPClient()

    started_at = perf_counter()

    try:
        tools = await client.list_tools()

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unavailable",
                "provider": "tutu_mcp",
                "error_type": (
                    type(exc).__name__
                ),
            },
        ) from exc

    latency_ms = int(
        (
            perf_counter()
            - started_at
        )
        * 1000
    )

    tool_names = [
        str(
            tool.get(
                "name",
                "unknown",
            )
        )
        for tool in tools
    ]

    return {
        "status": "connected",
        "provider": "tutu_mcp",
        "tools_count": len(tools),
        "tools": tool_names,
        "latency_ms": latency_ms,
    }