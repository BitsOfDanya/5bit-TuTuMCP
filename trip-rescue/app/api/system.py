from __future__ import annotations

import asyncio
import logging
import os
from time import (
    monotonic,
    perf_counter,
)

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)

from app.observability.metrics import (
    metrics_registry,
)
from app.tutu.client import (
    TutuMCPClient,
)


router = APIRouter(
    prefix="/api/v1/system",
    tags=["system"],
)


logger = logging.getLogger(
    "constraint_negotiator.system"
)


_mcp_cache_lock = (
    asyncio.Lock()
)

_mcp_tools_cache: list | None = None
_mcp_tools_cached_at: float | None = None


def _mcp_cache_ttl() -> float:
    return float(
        os.getenv(
            "MCP_TOOLS_CACHE_TTL_SECONDS",
            "300",
        )
    )


def _cache_is_valid() -> bool:
    if (
        _mcp_tools_cache is None
        or _mcp_tools_cached_at
        is None
    ):
        return False

    age = (
        monotonic()
        - _mcp_tools_cached_at
    )

    return (
        age
        < _mcp_cache_ttl()
    )


async def _load_mcp_tools(
    *,
    refresh: bool,
) -> tuple[
    list,
    bool,
]:
    global _mcp_tools_cache
    global _mcp_tools_cached_at

    if (
        not refresh
        and _cache_is_valid()
    ):
        return (
            _mcp_tools_cache or [],
            True,
        )

    async with _mcp_cache_lock:
        if (
            not refresh
            and _cache_is_valid()
        ):
            return (
                _mcp_tools_cache
                or [],
                True,
            )

        client = (
            TutuMCPClient()
        )

        tools = (
            await client.list_tools()
        )

        _mcp_tools_cache = tools

        _mcp_tools_cached_at = (
            monotonic()
        )

        return (
            tools,
            False,
        )


@router.get("/mcp")
async def mcp_status(
    refresh: bool = Query(
        default=False
    ),
) -> dict:

    started_at = (
        perf_counter()
    )

    try:
        tools, cached = (
            await _load_mcp_tools(
                refresh=refresh
            )
        )

    except Exception as exc:
        logger.exception(
            "Tutu MCP health check failed"
        )

        raise HTTPException(
            status_code=503,
            detail={
                "status": (
                    "unavailable"
                ),
                "provider": (
                    "tutu_mcp"
                ),
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
        "tools_count": (
            len(tool_names)
        ),
        "tools": tool_names,
        "cached": cached,
        "latency_ms": (
            latency_ms
        ),
    }


@router.get("/metrics")
async def runtime_metrics() -> dict:
    return (
        metrics_registry.snapshot()
    )