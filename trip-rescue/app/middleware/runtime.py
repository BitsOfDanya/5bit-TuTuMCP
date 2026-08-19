from __future__ import annotations

import asyncio
import json
import logging
import os
from collections import deque
from time import (
    monotonic,
    perf_counter,
)
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import (
    BaseHTTPMiddleware,
)
from starlette.responses import (
    JSONResponse,
    Response,
)

from app.observability.metrics import (
    metrics_registry,
)


logger = logging.getLogger(
    "constraint_negotiator.requests"
)


class RequestObservabilityMiddleware(
    BaseHTTPMiddleware
):
    async def dispatch(
        self,
        request: Request,
        call_next,
    ) -> Response:

        request_id = (
            request.headers.get(
                "X-Request-ID"
            )
            or uuid4().hex
        )

        started_at = (
            perf_counter()
        )

        status_code = 500

        try:
            response = (
                await call_next(
                    request
                )
            )

            status_code = (
                response.status_code
            )

        except Exception:
            duration_ms = (
                perf_counter()
                - started_at
            ) * 1000

            metrics_registry.record_request(
                path=request.url.path,
                status_code=500,
                duration_ms=duration_ms,
            )

            logger.exception(
                json.dumps(
                    {
                        "event": (
                            "request_failed"
                        ),
                        "request_id": (
                            request_id
                        ),
                        "method": (
                            request.method
                        ),
                        "path": (
                            request.url.path
                        ),
                        "status_code": 500,
                        "duration_ms": round(
                            duration_ms,
                            2,
                        ),
                    },
                    ensure_ascii=False,
                )
            )

            raise

        duration_ms = (
            perf_counter()
            - started_at
        ) * 1000

        metrics_registry.record_request(
            path=request.url.path,
            status_code=status_code,
            duration_ms=duration_ms,
        )

        response.headers[
            "X-Request-ID"
        ] = request_id

        logger.info(
            json.dumps(
                {
                    "event": (
                        "request_completed"
                    ),
                    "request_id": (
                        request_id
                    ),
                    "method": (
                        request.method
                    ),
                    "path": (
                        request.url.path
                    ),
                    "status_code": (
                        status_code
                    ),
                    "duration_ms": round(
                        duration_ms,
                        2,
                    ),
                },
                ensure_ascii=False,
            )
        )

        return response


class RateLimitMiddleware(
    BaseHTTPMiddleware
):
    """
    Lightweight per-process limiter.

    Enough for current single-container deployment.

    For multiple replicas this can later be moved
    to Redis/API Gateway without touching the
    negotiator core.
    """

    def __init__(
        self,
        app,
    ) -> None:
        super().__init__(app)

        self.limit = int(
            os.getenv(
                "NEGOTIATOR_RATE_LIMIT_PER_MINUTE",
                "60",
            )
        )

        self.window_seconds = 60.0

        self._requests: dict[
            str,
            deque[float],
        ] = {}

        self._lock = (
            asyncio.Lock()
        )

    async def dispatch(
        self,
        request: Request,
        call_next,
    ) -> Response:

        if not self._should_limit(
            request
        ):
            return await call_next(
                request
            )

        client = (
            request.client.host
            if request.client
            else "unknown"
        )

        now = monotonic()

        async with self._lock:
            history = (
                self._requests
                .setdefault(
                    client,
                    deque(),
                )
            )

            threshold = (
                now
                - self.window_seconds
            )

            while (
                history
                and history[0]
                <= threshold
            ):
                history.popleft()

            if (
                len(history)
                >= self.limit
            ):
                retry_after = max(
                    1,
                    int(
                        self.window_seconds
                        - (
                            now
                            - history[0]
                        )
                    ),
                )

                return JSONResponse(
                    status_code=429,
                    headers={
                        "Retry-After": str(
                            retry_after
                        )
                    },
                    content={
                        "detail": (
                            "Too many requests"
                        ),
                        "retry_after_seconds": (
                            retry_after
                        ),
                    },
                )

            history.append(
                now
            )

        return await call_next(
            request
        )

    def _should_limit(
        self,
        request: Request,
    ) -> bool:

        if self.limit <= 0:
            return False

        if (
            request.method
            == "OPTIONS"
        ):
            return False

        return (
            request.url.path
            .startswith(
                "/api/v1/negotiator/"
            )
        )