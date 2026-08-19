from __future__ import annotations

import json
import sys

import httpx


URL = (
    "http://127.0.0.1:8020"
    "/api/v1/rescue/from-text/public"
)


payload = {
    "current_trip": {
        "origin": "Москва",
        "destination": "Казань",
        "outbound_date": "2026-08-21",
        "return_date": "2026-08-23",
        "outbound_after": "19:00:00",
        "return_before": "22:00:00",
        "travelers": 2,
        "budget": 22703,
        "excluded_transport": [],
        "preferred_transport": [],
        "max_transfers": None,
        "hard_constraints": [],
    },

    "current_journey": {
        "id": "accepted-kazan-trip",
        "total_price": 22703,

        "outbound": {
            "id": "current-outbound-bus",
            "mode": "bus",
            "origin": (
                "Международный автовокзал "
                "Саларьево"
            ),
            "destination": (
                "Автовокзал Южный"
            ),
            "departure": (
                "2026-08-21T22:45:00+03:00"
            ),
            "arrival": (
                "2026-08-22T08:45:00+03:00"
            ),
            "price": 5000,
            "duration_minutes": 600,
            "transfers": 0,
            "carrier": "Евротранс",
        },

        "inbound": {
            "id": "current-inbound-flight",
            "mode": "flight",
            "origin": "Казань",
            "destination": "Москва",
            "departure": (
                "2026-08-23T07:05:00+03:00"
            ),
            "arrival": (
                "2026-08-23T08:40:00+03:00"
            ),
            "price": 14428,
            "duration_minutes": 95,
            "transfers": 0,
            "carrier": "Аэрофлот",
        },

        "hotel": {
            "id": "current-hotel",
            "name": (
                "Гостевой Дом Мансарда"
            ),
            "price": 3275,
            "stars": 0,
            "rating": 7.03,
            "review_count": 48,
            "check_in": "2026-08-22",
            "check_out": "2026-08-23",
            "nights": 1,
        },
    },

    # return_before = HARD
    # budget = intentionally SOFT and extremely low.
    "message": (
        "Планы поменялись. "
        "23 августа мне обязательно "
        "нужно быть в Москве до 8 утра, "
        "и желательно теперь уложиться "
        "максимум в 10 тысяч рублей."
    ),

    "reference_date": "2026-08-19",
}


def main() -> None:
    print()
    print("=" * 72)
    print(
        "TRIP RESCUE — NEGOTIATION FALLBACK"
    )
    print("=" * 72)

    with httpx.Client(
        timeout=180.0
    ) as client:
        response = client.post(
            URL,
            json=payload,
        )

    print(
        "HTTP:",
        response.status_code
    )

    data = response.json()

    print(
        "STATUS:",
        data.get(
            "status"
        )
    )

    print()

    if response.status_code >= 400:
        print(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
            )
        )
        sys.exit(1)

    candidates = (
        data.get(
            "candidates"
        )
        or []
    )

    print(
        "CANDIDATES:",
        len(candidates)
    )

    for index, candidate in enumerate(
        candidates,
        start=1,
    ):
        print()
        print(
            f"--- NEGOTIATION #{index} ---"
        )

        print(
            candidate[
                "summary"
            ][
                "headline"
            ]
        )

        print(
            candidate[
                "summary"
            ][
                "explanation"
            ]
        )

        print(
            "EXACT:",
            candidate.get(
                "exact"
            )
        )

        print(
            "TOTAL:",
            candidate[
                "journey"
            ][
                "total_price"
            ]
        )

        print(
            "RELAXATIONS:"
        )

        for relaxation in (
            candidate.get(
                "relaxations"
            )
            or []
        ):
            print(
                " ~",
                relaxation[
                    "field"
                ],
                ":",
                relaxation[
                    "description"
                ],
            )

        print(
            "SUGGESTED TRIP:"
        )

        print(
            json.dumps(
                candidate.get(
                    "suggested_trip"
                ),
                ensure_ascii=False,
                indent=2,
            )
        )

    print()
    print("=" * 72)

    if (
        data.get("status")
        == "negotiation_required"
    ):
        print(
            "NEGOTIATION FALLBACK: OK"
        )
    else:
        print(
            "Expected negotiation_required, "
            "got:",
            data.get("status"),
        )

    print("=" * 72)


if __name__ == "__main__":
    main()