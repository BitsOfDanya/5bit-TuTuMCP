from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from app.tutu.client import TutuMCPClient


OUTPUT_DIR = Path(
    "artifacts/tutu-hotels"
)


def save_json(
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


async def search_stay(
    client: TutuMCPClient,
    *,
    name: str,
    check_in: str,
    check_out: str,
) -> None:

    print()
    print("=" * 80)
    print(
        f"Searching hotel stay: "
        f"{check_in} -> {check_out}"
    )
    print("=" * 80)

    raw = await client.call_tool_raw(
        name="search_hotels",
        arguments={
            "city_name": "Казань",
            "check_in": check_in,
            "check_out": check_out,
            "adults": 2,

            # Нужен широкий candidate pool,
            # но пока без лишних данных.
            "page": 1,
            "page_size": 10,
            "view": "compact",
        },
    )

    payload = (
        client._extract_payload(
            raw
        )
    )

    save_json(
        f"{name}_raw.json",
        raw,
    )

    save_json(
        f"{name}.json",
        payload,
    )

    print(
        "Top-level keys:",
        list(payload.keys()),
    )

    hotels = payload.get(
        "hotels",
        []
    )

    print(
        "Hotels:",
        len(hotels)
        if isinstance(hotels, list)
        else "unknown",
    )

    if (
        isinstance(hotels, list)
        and hotels
    ):
        print()
        print(
            "First hotel:"
        )

        print(
            json.dumps(
                hotels[0],
                ensure_ascii=False,
                indent=2,
            )[:8000]
        )


async def main() -> None:
    client = TutuMCPClient()

    # Вариант с самолётом:
    #
    # прилёт 21 августа 23:20
    # обратный вылет 23 августа 07:05
    await search_stay(
        client,
        name="stay_21_23",
        check_in="2026-08-21",
        check_out="2026-08-23",
    )

    # Вариант с автобусом:
    #
    # приезд 22 августа 08:45
    # обратный вылет 23 августа 07:05
    await search_stay(
        client,
        name="stay_22_23",
        check_in="2026-08-22",
        check_out="2026-08-23",
    )


if __name__ == "__main__":
    asyncio.run(main())