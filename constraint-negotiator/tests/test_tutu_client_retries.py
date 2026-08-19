from __future__ import annotations

import asyncio

import httpx

from app.tutu.client import (
    TutuMCPClient,
    TutuMCPError,
)


def test_transient_connect_error_is_retried() -> None:
    async def run() -> None:
        client = TutuMCPClient(
            url="http://test.invalid/mcp"
        )

        client.max_attempts = 3
        client.operation_timeout_seconds = 2.0
        client.retry_base_delay_seconds = 0.001
        client.retry_max_delay_seconds = 0.001

        attempts = 0

        async def action() -> dict:
            nonlocal attempts

            attempts += 1

            if attempts < 3:
                request = httpx.Request(
                    "POST",
                    "http://test.invalid/mcp",
                )

                raise httpx.ConnectError(
                    "temporary failure",
                    request=request,
                )

            return {
                "status": "ok"
            }

        result = await (
            client._run_with_retries(
                metric_name=(
                    "test_transient"
                ),
                operation_name=(
                    "test_transient"
                ),
                action=action,
            )
        )

        assert result == {
            "status": "ok"
        }

        assert attempts == 3

    asyncio.run(
        run()
    )


def test_mcp_tool_error_is_not_retried() -> None:
    async def run() -> None:
        client = TutuMCPClient(
            url="http://test.invalid/mcp"
        )

        client.max_attempts = 3
        client.operation_timeout_seconds = 2.0
        client.retry_base_delay_seconds = 0.001

        attempts = 0

        async def action() -> dict:
            nonlocal attempts

            attempts += 1

            raise TutuMCPError(
                "bad tool request"
            )

        try:
            await client._run_with_retries(
                metric_name=(
                    "test_non_transient"
                ),
                operation_name=(
                    "test_non_transient"
                ),
                action=action,
            )

        except TutuMCPError:
            pass

        else:
            raise AssertionError(
                "Expected TutuMCPError"
            )

        assert attempts == 1

    asyncio.run(
        run()
    )


def test_timeout_is_classified_as_transient() -> None:
    assert (
        TutuMCPClient
        ._is_transient_error(
            TimeoutError()
        )
        is True
    )


def test_tool_error_is_not_transient() -> None:
    assert (
        TutuMCPClient
        ._is_transient_error(
            TutuMCPError(
                "tool failed"
            )
        )
        is False
    )