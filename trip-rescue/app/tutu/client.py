from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import (
    Awaitable,
    Callable,
)
from time import (
    monotonic,
    perf_counter,
)
from typing import (
    Any,
    TypeVar,
)

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import (
    streamable_http_client,
)

from app.config import get_settings
from app.observability.metrics import (
    metrics_registry,
)


logger = logging.getLogger(
    "constraint_negotiator.tutu_mcp"
)


T = TypeVar("T")


class TutuMCPError(RuntimeError):
    pass


class TutuMCPClient:
    """
    Tutu MCP client with:

    - explicit HTTP timeouts;
    - overall operation deadline;
    - retries for transient transport failures only;
    - exponential backoff;
    - structured logs;
    - per-tool latency/error/retry metrics.

    Application-level MCP tool errors are NOT retried.
    """

    def __init__(
        self,
        url: str | None = None,
    ) -> None:
        settings = get_settings()

        self.url = (
            url
            or settings.tutu_mcp_url
        )

        self.connect_timeout_seconds = (
            self._env_float(
                "MCP_CONNECT_TIMEOUT_SECONDS",
                10.0,
            )
        )

        self.read_timeout_seconds = (
            self._env_float(
                "MCP_READ_TIMEOUT_SECONDS",
                90.0,
            )
        )

        self.write_timeout_seconds = (
            self._env_float(
                "MCP_WRITE_TIMEOUT_SECONDS",
                30.0,
            )
        )

        self.pool_timeout_seconds = (
            self._env_float(
                "MCP_POOL_TIMEOUT_SECONDS",
                10.0,
            )
        )

        self.operation_timeout_seconds = (
            self._env_float(
                "MCP_OPERATION_TIMEOUT_SECONDS",
                120.0,
            )
        )

        self.max_attempts = (
            self._env_int(
                "MCP_MAX_ATTEMPTS",
                3,
            )
        )

        self.retry_base_delay_seconds = (
            self._env_float(
                "MCP_RETRY_BASE_DELAY_SECONDS",
                0.5,
            )
        )

        self.retry_max_delay_seconds = (
            self._env_float(
                "MCP_RETRY_MAX_DELAY_SECONDS",
                4.0,
            )
        )

    # =========================================================
    # Public API
    # =========================================================

    async def list_tools(
        self,
    ) -> list[dict[str, Any]]:

        return await self._run_with_retries(
            metric_name="list_tools",
            operation_name="list_tools",
            action=self._list_tools_once,
        )

    async def call_tool_raw(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:

        async def action() -> dict[str, Any]:
            return await (
                self._call_tool_raw_once(
                    name=name,
                    arguments=arguments,
                )
            )

        return await self._run_with_retries(
            metric_name=name,
            operation_name=(
                f"call_tool:{name}"
            ),
            action=action,
        )

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:

        raw = await self.call_tool_raw(
            name=name,
            arguments=arguments,
        )

        return self._extract_payload(
            raw
        )

    # =========================================================
    # One-shot MCP operations
    # =========================================================

    async def _list_tools_once(
        self,
    ) -> list[dict[str, Any]]:

        async with (
            self._create_http_client()
            as http_client
        ):
            async with (
                streamable_http_client(
                    self.url,
                    http_client=http_client,
                )
            ) as streams:

                read_stream = (
                    streams[0]
                )

                write_stream = (
                    streams[1]
                )

                async with ClientSession(
                    read_stream,
                    write_stream,
                ) as session:

                    await (
                        session.initialize()
                    )

                    tools: list[
                        dict[str, Any]
                    ] = []

                    cursor: (
                        str | None
                    ) = None

                    while True:
                        result = (
                            await session.list_tools(
                                cursor=cursor
                            )
                        )

                        for tool in (
                            result.tools
                        ):
                            tools.append(
                                tool.model_dump(
                                    mode="json",
                                    by_alias=True,
                                )
                            )

                        next_cursor = (
                            getattr(
                                result,
                                "next_cursor",
                                None,
                            )
                        )

                        if (
                            next_cursor
                            is None
                        ):
                            next_cursor = (
                                getattr(
                                    result,
                                    "nextCursor",
                                    None,
                                )
                            )

                        if not next_cursor:
                            break

                        cursor = (
                            next_cursor
                        )

                    return tools

    async def _call_tool_raw_once(
        self,
        *,
        name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:

        async with (
            self._create_http_client()
            as http_client
        ):
            async with (
                streamable_http_client(
                    self.url,
                    http_client=http_client,
                )
            ) as streams:

                read_stream = (
                    streams[0]
                )

                write_stream = (
                    streams[1]
                )

                async with ClientSession(
                    read_stream,
                    write_stream,
                ) as session:

                    await (
                        session.initialize()
                    )

                    result = (
                        await session.call_tool(
                            name=name,
                            arguments=arguments,
                        )
                    )

                    if getattr(
                        result,
                        "isError",
                        False,
                    ):
                        # MCP application/tool errors
                        # are intentionally NOT retryable.
                        raise TutuMCPError(
                            "Tutu MCP tool "
                            f"failed: {name}"
                        )

                    if not hasattr(
                        result,
                        "model_dump",
                    ):
                        raise TutuMCPError(
                            "Unsupported MCP "
                            "result for tool: "
                            f"{name}"
                        )

                    return (
                        result.model_dump(
                            mode="json",
                            by_alias=True,
                        )
                    )

    # =========================================================
    # Retry layer
    # =========================================================

    async def _run_with_retries(
        self,
        *,
        metric_name: str,
        operation_name: str,
        action: Callable[
            [],
            Awaitable[T],
        ],
    ) -> T:

        started_at = (
            perf_counter()
        )

        deadline = (
            monotonic()
            + self.operation_timeout_seconds
        )

        retries = 0

        for attempt in range(
            1,
            self.max_attempts + 1,
        ):
            remaining_seconds = (
                deadline
                - monotonic()
            )

            if remaining_seconds <= 0:
                exc = TimeoutError(
                    "Tutu MCP operation "
                    "deadline exceeded"
                )

                self._record_failure(
                    metric_name=metric_name,
                    started_at=started_at,
                    retries=retries,
                )

                raise exc

            attempt_started_at = (
                perf_counter()
            )

            try:
                async with asyncio.timeout(
                    remaining_seconds
                ):
                    result = (
                        await action()
                    )

            except Exception as exc:
                transient = (
                    self._is_transient_error(
                        exc
                    )
                )

                is_last_attempt = (
                    attempt
                    >= self.max_attempts
                )

                if (
                    not transient
                    or is_last_attempt
                ):
                    duration_ms = (
                        (
                            perf_counter()
                            - started_at
                        )
                        * 1000
                    )

                    metrics_registry.record_mcp_call(
                        tool_name=metric_name,
                        success=False,
                        duration_ms=duration_ms,
                        retries=retries,
                    )

                    logger.error(
                        (
                            "mcp_call_failed "
                            "operation=%s "
                            "attempt=%d "
                            "retries=%d "
                            "duration_ms=%.2f "
                            "error_type=%s"
                        ),
                        operation_name,
                        attempt,
                        retries,
                        duration_ms,
                        type(exc).__name__,
                        exc_info=True,
                    )

                    raise

                delay_seconds = min(
                    (
                        self.retry_base_delay_seconds
                        * (
                            2
                            ** (
                                attempt
                                - 1
                            )
                        )
                    ),
                    self.retry_max_delay_seconds,
                )

                remaining_after_error = (
                    deadline
                    - monotonic()
                )

                if (
                    remaining_after_error
                    <= delay_seconds
                ):
                    duration_ms = (
                        (
                            perf_counter()
                            - started_at
                        )
                        * 1000
                    )

                    metrics_registry.record_mcp_call(
                        tool_name=metric_name,
                        success=False,
                        duration_ms=duration_ms,
                        retries=retries,
                    )

                    logger.error(
                        (
                            "mcp_call_deadline "
                            "operation=%s "
                            "attempt=%d "
                            "duration_ms=%.2f"
                        ),
                        operation_name,
                        attempt,
                        duration_ms,
                    )

                    raise

                attempt_duration_ms = (
                    (
                        perf_counter()
                        - attempt_started_at
                    )
                    * 1000
                )

                retries += 1

                logger.warning(
                    (
                        "mcp_call_retry "
                        "operation=%s "
                        "attempt=%d "
                        "next_attempt=%d "
                        "delay_seconds=%.2f "
                        "attempt_duration_ms=%.2f "
                        "error_type=%s"
                    ),
                    operation_name,
                    attempt,
                    attempt + 1,
                    delay_seconds,
                    attempt_duration_ms,
                    type(exc).__name__,
                )

                await asyncio.sleep(
                    delay_seconds
                )

                continue

            duration_ms = (
                (
                    perf_counter()
                    - started_at
                )
                * 1000
            )

            metrics_registry.record_mcp_call(
                tool_name=metric_name,
                success=True,
                duration_ms=duration_ms,
                retries=retries,
            )

            logger.info(
                (
                    "mcp_call_completed "
                    "operation=%s "
                    "attempt=%d "
                    "retries=%d "
                    "duration_ms=%.2f"
                ),
                operation_name,
                attempt,
                retries,
                duration_ms,
            )

            return result

        # Defensive fallback.
        raise RuntimeError(
            "Unexpected MCP retry state"
        )

    # =========================================================
    # HTTP
    # =========================================================

    def _create_http_client(
        self,
    ) -> httpx.AsyncClient:

        timeout = httpx.Timeout(
            connect=(
                self.connect_timeout_seconds
            ),
            read=(
                self.read_timeout_seconds
            ),
            write=(
                self.write_timeout_seconds
            ),
            pool=(
                self.pool_timeout_seconds
            ),
        )

        return httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
        )

    # =========================================================
    # Error classification
    # =========================================================

    @classmethod
    def _is_transient_error(
        cls,
        exc: BaseException,
    ) -> bool:

        # MCP tool/application errors are not
        # transport failures and must not be retried.
        if isinstance(
            exc,
            TutuMCPError,
        ):
            return False

        if isinstance(
            exc,
            TimeoutError,
        ):
            return True

        if isinstance(
            exc,
            httpx.TimeoutException,
        ):
            return True

        if isinstance(
            exc,
            httpx.TransportError,
        ):
            return True

        if isinstance(
            exc,
            httpx.HTTPStatusError,
        ):
            status_code = (
                exc.response.status_code
            )

            return (
                status_code
                in {
                    408,
                    425,
                    429,
                    500,
                    502,
                    503,
                    504,
                }
            )

        # MCP/AnyIO can wrap the original HTTP
        # problem inside an ExceptionGroup.
        if isinstance(
            exc,
            BaseExceptionGroup,
        ):
            return any(
                cls._is_transient_error(
                    child
                )
                for child
                in exc.exceptions
            )

        return False

    # =========================================================
    # Payload parsing
    # =========================================================

    @staticmethod
    def _extract_payload(
        raw: dict[str, Any],
    ) -> dict[str, Any]:

        structured = (
            raw.get(
                "structuredContent"
            )
            or raw.get(
                "structured_content"
            )
        )

        if isinstance(
            structured,
            dict,
        ):
            return structured

        content = raw.get(
            "content"
        )

        if not isinstance(
            content,
            list,
        ):
            return raw

        for block in content:
            if not isinstance(
                block,
                dict,
            ):
                continue

            text = block.get(
                "text"
            )

            if not isinstance(
                text,
                str,
            ):
                continue

            text = (
                text.strip()
            )

            if not text:
                continue

            try:
                parsed = (
                    json.loads(
                        text
                    )
                )

            except json.JSONDecodeError:
                continue

            if isinstance(
                parsed,
                dict,
            ):
                return parsed

        return raw

    # =========================================================
    # Helpers
    # =========================================================

    def _record_failure(
        self,
        *,
        metric_name: str,
        started_at: float,
        retries: int,
    ) -> None:

        duration_ms = (
            (
                perf_counter()
                - started_at
            )
            * 1000
        )

        metrics_registry.record_mcp_call(
            tool_name=metric_name,
            success=False,
            duration_ms=duration_ms,
            retries=retries,
        )

    @staticmethod
    def _env_float(
        name: str,
        default: float,
    ) -> float:

        raw = os.getenv(
            name
        )

        if raw is None:
            return default

        try:
            value = float(
                raw
            )

        except ValueError:
            logger.warning(
                (
                    "Invalid %s=%r; "
                    "using default=%s"
                ),
                name,
                raw,
                default,
            )

            return default

        if value <= 0:
            return default

        return value

    @staticmethod
    def _env_int(
        name: str,
        default: int,
    ) -> int:

        raw = os.getenv(
            name
        )

        if raw is None:
            return default

        try:
            value = int(
                raw
            )

        except ValueError:
            logger.warning(
                (
                    "Invalid %s=%r; "
                    "using default=%s"
                ),
                name,
                raw,
                default,
            )

            return default

        if value <= 0:
            return default

        return value