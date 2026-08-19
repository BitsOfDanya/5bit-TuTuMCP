import asyncio
import json
from pathlib import Path
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


TUTU_MCP_URL = "https://mcp.tutu.ru/mcp"

OUTPUT_PATH = Path(
    "artifacts/tutu_mcp_tools.json"
)


def serialize_tool(tool: Any) -> dict[str, Any]:
    if hasattr(tool, "model_dump"):
        return tool.model_dump(
            mode="json",
            by_alias=True,
        )

    return {
        "name": getattr(tool, "name", None),
        "title": getattr(tool, "title", None),
        "description": getattr(
            tool,
            "description",
            None,
        ),
        "inputSchema": getattr(
            tool,
            "inputSchema",
            getattr(
                tool,
                "input_schema",
                None,
            ),
        ),
    }


async def main() -> None:
    print(
        f"Connecting to Tutu MCP:\n"
        f"{TUTU_MCP_URL}\n"
    )

    async with streamable_http_client(
        TUTU_MCP_URL
    ) as streams:

        read_stream = streams[0]
        write_stream = streams[1]

        async with ClientSession(
            read_stream,
            write_stream,
        ) as session:

            init_result = await session.initialize()

            print("Connected.")
            print()

            server_info = getattr(
                init_result,
                "serverInfo",
                getattr(
                    init_result,
                    "server_info",
                    None,
                ),
            )

            if server_info:
                print("Server info:")
                print(server_info)
                print()

            tools: list[Any] = []
            cursor: str | None = None

            while True:
                result = await session.list_tools(
                    cursor=cursor
                )

                tools.extend(result.tools)

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

    serialized = [
        serialize_tool(tool)
        for tool in tools
    ]

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            serialized,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"Found tools: {len(serialized)}"
    )

    print(
        "=" * 80
    )

    for index, tool in enumerate(
        serialized,
        start=1,
    ):
        print()
        print(
            f"[{index}] "
            f"{tool.get('name')}"
        )

        title = tool.get("title")

        if title:
            print(
                f"Title: {title}"
            )

        description = tool.get(
            "description"
        )

        if description:
            print(
                f"Description:\n"
                f"{description}"
            )

        schema = (
            tool.get("inputSchema")
            or tool.get("input_schema")
        )

        print(
            "Input schema:"
        )

        print(
            json.dumps(
                schema,
                ensure_ascii=False,
                indent=2,
            )
        )

        print(
            "-" * 80
        )

    print()
    print(
        f"Saved to: {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    asyncio.run(main())