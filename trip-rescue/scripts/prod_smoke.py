from __future__ import annotations

import os
import sys
from urllib.parse import urljoin

import httpx


BASE_URL = (
    os.getenv(
        "TRIP_RESCUE_URL",
        "http://127.0.0.1:8020",
    )
    .rstrip("/")
)


def fail(
    message: str,
) -> None:
    print(
        f"FAILED: {message}"
    )
    sys.exit(1)


def main() -> None:
    print(
        "Trip Rescue production smoke"
    )

    print(
        f"BASE_URL={BASE_URL}"
    )

    with httpx.Client(
        timeout=30.0,
    ) as client:
        health = client.get(
            urljoin(
                f"{BASE_URL}/",
                "health",
            )
        )

        if (
            health.status_code
            != 200
        ):
            fail(
                "health returned "
                f"{health.status_code}"
            )

        health_data = (
            health.json()
        )

        if (
            health_data.get(
                "status"
            )
            != "ok"
        ):
            fail(
                "health status "
                "is not ok"
            )

        print(
            "HEALTH: OK"
        )

        ready = client.get(
            urljoin(
                f"{BASE_URL}/",
                "ready",
            )
        )

        if (
            ready.status_code
            != 200
        ):
            fail(
                "ready returned "
                f"{ready.status_code}"
            )

        ready_data = (
            ready.json()
        )

        if (
            ready_data.get(
                "status"
            )
            != "ready"
        ):
            fail(
                "service is not ready"
            )

        print(
            "READY: OK"
        )

        mcp = client.get(
            urljoin(
                f"{BASE_URL}/",
                "api/v1/system/mcp",
            ),
            params={
                "refresh": "true",
            },
        )

        if (
            mcp.status_code
            != 200
        ):
            fail(
                "MCP diagnostics returned "
                f"{mcp.status_code}"
            )

        mcp_data = (
            mcp.json()
        )

        if (
            mcp_data.get(
                "status"
            )
            != "connected"
        ):
            fail(
                "Tutu MCP is not connected"
            )

        tools_count = (
            mcp_data.get(
                "tools_count",
                0,
            )
        )

        if tools_count <= 0:
            fail(
                "MCP has no tools"
            )

        print(
            "MCP: OK"
        )

        print(
            f"MCP TOOLS: {tools_count}"
        )

    print()
    print(
        "PRODUCTION SMOKE: OK"
    )


if __name__ == "__main__":
    main()