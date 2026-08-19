from __future__ import annotations

import json
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from app.config import get_settings


class TutuMCPError(RuntimeError):
    pass


class TutuMCPClient:
    def __init__(
        self,
        url: str | None = None,
    ) -> None:
        settings = get_settings()

        self.url = url or settings.tutu_mcp_url

    async def list_tools(
        self,
    ) -> list[dict[str, Any]]:
        async with streamable_http_client(
            self.url
        ) as streams:
            read_stream = streams[0]
            write_stream = streams[1]

            async with ClientSession(
                read_stream,
                write_stream,
            ) as session:
                await session.initialize()

                tools: list[dict[str, Any]] = []
                cursor: str | None = None

                while True:
                    result = await session.list_tools(
                        cursor=cursor
                    )

                    for tool in result.tools:
                        tools.append(
                            tool.model_dump(
                                mode="json",
                                by_alias=True,
                            )
                        )

                    next_cursor = getattr(
                        result,
                        "next_cursor",
                        None,
                    )

                    if next_cursor is None:
                        next_cursor = getattr(
                            result,
                            "nextCursor",
                            None,
                        )

                    if not next_cursor:
                        break

                    cursor = next_cursor

                return tools

    async def call_tool_raw(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        async with streamable_http_client(
            self.url
        ) as streams:
            read_stream = streams[0]
            write_stream = streams[1]

            async with ClientSession(
                read_stream,
                write_stream,
            ) as session:
                await session.initialize()

                result = await session.call_tool(
                    name=name,
                    arguments=arguments,
                )

                if getattr(
                    result,
                    "isError",
                    False,
                ):
                    raise TutuMCPError(
                        f"Tutu MCP tool failed: {name}"
                    )

                if not hasattr(
                    result,
                    "model_dump",
                ):
                    raise TutuMCPError(
                        f"Unsupported MCP result "
                        f"for tool: {name}"
                    )

                return result.model_dump(
                    mode="json",
                    by_alias=True,
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

        return self._extract_payload(raw)

    @staticmethod
    def _extract_payload(
        raw: dict[str, Any],
    ) -> dict[str, Any]:
        structured = (
            raw.get("structuredContent")
            or raw.get("structured_content")
        )

        if isinstance(structured, dict):
            return structured

        content = raw.get("content")

        if not isinstance(content, list):
            return raw

        for block in content:
            if not isinstance(block, dict):
                continue

            text = block.get("text")

            if not isinstance(text, str):
                continue

            text = text.strip()

            if not text:
                continue

            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                continue

            if isinstance(parsed, dict):
                return parsed

        return raw