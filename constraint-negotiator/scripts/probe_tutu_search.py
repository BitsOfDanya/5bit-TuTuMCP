from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from app.tutu.client import TutuMCPClient


OUTPUT_DIR = Path(
    "artifacts/tutu-search"
)


async def save_json(
    filename: str,
    payload: Any,
) -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = OUTPUT_DIR / filename

    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"Saved: {path}"
    )


async def main() -> None:
    client = TutuMCPClient()

    outbound_args = {
        "origin": "Москва",
        "destination": "Казань",
        "departure_date": "2026-08-21",
        "adults": 2,
        "modes": [
            "avia",
            "railway",
            "bus",
            "etrain",
        ],
        "optimize_for": "price",
        "page": 1,
        "page_size": 10,
        "direct_only": False,
        "view": "compact",
    }

    inbound_args = {
        "origin": "Казань",
        "destination": "Москва",
        "departure_date": "2026-08-23",
        "adults": 2,
        "modes": [
            "avia",
            "railway",
            "bus",
            "etrain",
        ],
        "optimize_for": "price",
        "page": 1,
        "page_size": 10,
        "direct_only": False,
        "view": "compact",
    }

    print(
        "Searching outbound + inbound..."
    )

    outbound_task = client.call_tool_raw(
        name="search_multitransport",
        arguments=outbound_args,
    )

    inbound_task = client.call_tool_raw(
        name="search_multitransport",
        arguments=inbound_args,
    )

    outbound_raw, inbound_raw = (
        await asyncio.gather(
            outbound_task,
            inbound_task,
        )
    )

    await save_json(
        "outbound_raw.json",
        outbound_raw,
    )

    await save_json(
        "inbound_raw.json",
        inbound_raw,
    )

    print()
    print(
        "Now extracting payloads..."
    )

    outbound = (
        client._extract_payload(
            outbound_raw
        )
    )

    inbound = (
        client._extract_payload(
            inbound_raw
        )
    )

    await save_json(
        "outbound.json",
        outbound,
    )

    await save_json(
        "inbound.json",
        inbound,
    )

    print()
    print(
        "Outbound top-level keys:"
    )
    print(
        list(outbound.keys())
    )

    print()
    print(
        "Inbound top-level keys:"
    )
    print(
        list(inbound.keys())
    )

    outbound_variants = (
        outbound.get("variants", [])
    )

    inbound_variants = (
        inbound.get("variants", [])
    )

    print()
    print(
        "Outbound variants:",
        len(outbound_variants),
    )

    print(
        "Inbound variants:",
        len(inbound_variants),
    )

    if outbound_variants:
        print()
        print(
            "First outbound variant:"
        )
        print(
            json.dumps(
                outbound_variants[0],
                ensure_ascii=False,
                indent=2,
            )[:6000]
        )

    if inbound_variants:
        print()
        print(
            "First inbound variant:"
        )
        print(
            json.dumps(
                inbound_variants[0],
                ensure_ascii=False,
                indent=2,
            )[:6000]
        )


if __name__ == "__main__":
    asyncio.run(main())