from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from time import time


@dataclass
class RouteMetrics:
    requests: int = 0
    errors: int = 0

    total_duration_ms: float = 0.0
    max_duration_ms: float = 0.0

    def record(
        self,
        *,
        status_code: int,
        duration_ms: float,
    ) -> None:
        self.requests += 1

        if status_code >= 500:
            self.errors += 1

        self.total_duration_ms += (
            duration_ms
        )

        self.max_duration_ms = max(
            self.max_duration_ms,
            duration_ms,
        )

    def dump(self) -> dict:
        average = (
            self.total_duration_ms
            / self.requests
            if self.requests
            else 0.0
        )

        return {
            "requests": self.requests,
            "errors": self.errors,
            "average_duration_ms": round(
                average,
                2,
            ),
            "max_duration_ms": round(
                self.max_duration_ms,
                2,
            ),
        }


@dataclass
class MCPCallMetrics:
    calls: int = 0
    errors: int = 0
    retries: int = 0

    total_duration_ms: float = 0.0
    max_duration_ms: float = 0.0

    def record(
        self,
        *,
        success: bool,
        duration_ms: float,
        retries: int,
    ) -> None:
        self.calls += 1

        if not success:
            self.errors += 1

        self.retries += retries

        self.total_duration_ms += (
            duration_ms
        )

        self.max_duration_ms = max(
            self.max_duration_ms,
            duration_ms,
        )

    def dump(self) -> dict:
        average = (
            self.total_duration_ms
            / self.calls
            if self.calls
            else 0.0
        )

        return {
            "calls": self.calls,
            "errors": self.errors,
            "retries": self.retries,
            "average_duration_ms": round(
                average,
                2,
            ),
            "max_duration_ms": round(
                self.max_duration_ms,
                2,
            ),
        }


class MetricsRegistry:
    def __init__(self) -> None:
        self._started_at = time()

        self._routes: dict[
            str,
            RouteMetrics,
        ] = {}

        self._mcp_calls: dict[
            str,
            MCPCallMetrics,
        ] = {}

        self._lock = Lock()

    def record_request(
        self,
        *,
        path: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        with self._lock:
            route = (
                self._routes
                .setdefault(
                    path,
                    RouteMetrics(),
                )
            )

            route.record(
                status_code=status_code,
                duration_ms=duration_ms,
            )

    def record_mcp_call(
        self,
        *,
        tool_name: str,
        success: bool,
        duration_ms: float,
        retries: int,
    ) -> None:
        with self._lock:
            metrics = (
                self._mcp_calls
                .setdefault(
                    tool_name,
                    MCPCallMetrics(),
                )
            )

            metrics.record(
                success=success,
                duration_ms=duration_ms,
                retries=retries,
            )

    def snapshot(self) -> dict:
        with self._lock:
            routes = {
                path: metrics.dump()
                for path, metrics
                in sorted(
                    self._routes.items()
                )
            }

            mcp_calls = {
                tool_name: metrics.dump()
                for tool_name, metrics
                in sorted(
                    self._mcp_calls.items()
                )
            }

        uptime_seconds = int(
            time()
            - self._started_at
        )

        total_requests = sum(
            route["requests"]
            for route
            in routes.values()
        )

        total_errors = sum(
            route["errors"]
            for route
            in routes.values()
        )

        total_mcp_calls = sum(
            item["calls"]
            for item
            in mcp_calls.values()
        )

        total_mcp_errors = sum(
            item["errors"]
            for item
            in mcp_calls.values()
        )

        total_mcp_retries = sum(
            item["retries"]
            for item
            in mcp_calls.values()
        )

        return {
            "uptime_seconds": (
                uptime_seconds
            ),
            "requests": (
                total_requests
            ),
            "errors": (
                total_errors
            ),
            "routes": routes,
            "mcp": {
                "calls": (
                    total_mcp_calls
                ),
                "errors": (
                    total_mcp_errors
                ),
                "retries": (
                    total_mcp_retries
                ),
                "tools": (
                    mcp_calls
                ),
            },
        }


metrics_registry = (
    MetricsRegistry()
)