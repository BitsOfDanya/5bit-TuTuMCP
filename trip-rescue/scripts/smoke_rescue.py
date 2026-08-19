from __future__ import annotations

import json
import sys
from typing import Any

import httpx


BASE_URL = "http://127.0.0.1:8020"

ENDPOINT = (
    f"{BASE_URL}"
    "/api/v1/rescue/from-text/public"
)


CURRENT_TRIP = {
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
}


CURRENT_JOURNEY = {
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
        "voyage_no": None,
        "rating": 8.6,
        "review_count": 2971,
        "booking_url": None,
    },

    "inbound": {
        "id": "current-inbound-flight",
        "mode": "flight",
        "origin": "Казань, KZN",
        "destination": (
            "Москва — Шереметьево (SVO)"
        ),
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
        "voyage_no": "SU-1199",
        "rating": 9.25,
        "review_count": 22870,
        "booking_url": None,
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
        "address": (
            "2.6 км от центра"
        ),
        "room_name": (
            "3-местный номер эконом"
        ),
        "check_in": "2026-08-22",
        "check_out": "2026-08-23",
        "nights": 1,
        "booking_url": None,
        "photo_url": None,
    },
}


PAYLOAD = {
    "current_trip": CURRENT_TRIP,
    "current_journey": CURRENT_JOURNEY,
    "message": (
        "Планы поменялись. "
        "23 августа мне теперь обязательно "
        "нужно быть в Москве до 8 утра."
    ),
    "reference_date": "2026-08-19",
}


def main() -> None:
    print()
    print("=" * 68)
    print("TRIP RESCUE — REAL END-TO-END SMOKE")
    print("=" * 68)

    print()
    print("CURRENT JOURNEY")
    print("-" * 68)
    print(
        "OUTBOUND : "
        "Москва → Казань | "
        "автобус | "
        "21.08 22:45"
    )
    print(
        "HOTEL    : "
        "Гостевой Дом Мансарда | "
        "3 275 ₽"
    )
    print(
        "INBOUND  : "
        "Казань → Москва | "
        "08:40 arrival"
    )
    print(
        "TOTAL    : "
        "22 703 ₽"
    )

    print()
    print("USER UPDATE")
    print("-" * 68)
    print(
        PAYLOAD["message"]
    )

    print()
    print("Calling:")
    print(ENDPOINT)
    print()

    try:
        with httpx.Client(
            timeout=httpx.Timeout(
                180.0
            )
        ) as client:
            response = client.post(
                ENDPOINT,
                json=PAYLOAD,
            )

    except Exception as exc:
        print(
            "REQUEST FAILED:",
            type(exc).__name__,
            str(exc),
        )
        sys.exit(1)

    print(
        "HTTP:",
        response.status_code,
    )

    try:
        data: dict[str, Any] = (
            response.json()
        )

    except Exception:
        print()
        print(
            "NON-JSON RESPONSE:"
        )
        print(
            response.text
        )
        sys.exit(1)

    if response.status_code >= 400:
        print()
        print("ERROR RESPONSE")
        print("-" * 68)
        print(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
            )
        )
        sys.exit(1)

    print()
    print("RESCUE RESULT")
    print("=" * 68)

    print(
        "STATUS:",
        data.get(
            "status"
        ),
    )

    updated_trip = (
        data.get(
            "updated_trip"
        )
        or {}
    )

    print()
    print("UPDATED CONSTRAINTS")
    print("-" * 68)

    print(
        "return_before:",
        updated_trip.get(
            "return_before"
        ),
    )

    print(
        "hard_constraints:",
        updated_trip.get(
            "hard_constraints"
        ),
    )

    print()
    print("CHANGED")
    print("-" * 68)

    changed_fields = (
        data.get(
            "changed_fields"
        )
        or []
    )

    if changed_fields:
        for field in changed_fields:
            print(
                "•",
                field,
            )
    else:
        print(
            "nothing"
        )

    print()
    print("PRESERVE")
    print("-" * 68)

    preserved = (
        data.get(
            "preserved_components"
        )
        or []
    )

    if preserved:
        for component in preserved:
            print(
                "✓",
                component,
            )
    else:
        print(
            "nothing"
        )

    print()
    print("REPLACE")
    print("-" * 68)

    replaced = (
        data.get(
            "replace_components"
        )
        or []
    )

    if replaced:
        for component in replaced:
            print(
                "✕",
                component,
            )
    else:
        print(
            "nothing"
        )

    print()
    print("WHY")
    print("-" * 68)

    reasons = (
        data.get(
            "reasons"
        )
        or []
    )

    if reasons:
        for reason in reasons:
            print(
                "•",
                reason,
            )
    else:
        print(
            "No validation problems."
        )

    candidates = (
        data.get(
            "candidates"
        )
        or []
    )

    print()
    print(
        "CANDIDATES:",
        len(candidates),
    )

    print("=" * 68)

    for index, candidate in enumerate(
        candidates,
        start=1,
    ):
        print()
        print(
            f"CANDIDATE #{index}"
        )
        print("-" * 68)

        summary = (
            candidate.get(
                "summary"
            )
            or {}
        )

        print(
            summary.get(
                "headline",
                "—",
            )
        )

        print(
            summary.get(
                "explanation",
                "—",
            )
        )

        print(
            "Price:",
            summary.get(
                "previous_total_price"
            ),
            "→",
            summary.get(
                "new_total_price"
            ),
            "("
            + str(
                summary.get(
                    "price_delta_label"
                )
            )
            + ")",
        )

        journey = (
            candidate.get(
                "journey"
            )
            or {}
        )

        outbound = (
            journey.get(
                "outbound"
            )
            or {}
        )

        hotel = (
            journey.get(
                "hotel"
            )
        )

        inbound = (
            journey.get(
                "inbound"
            )
            or {}
        )

        print()
        print(
            "OUTBOUND:"
        )

        print(
            " ",
            outbound.get(
                "mode"
            ),
            "|",
            outbound.get(
                "departure"
            ),
            "→",
            outbound.get(
                "arrival"
            ),
            "|",
            outbound.get(
                "price"
            ),
            "₽",
        )

        print()
        print(
            "HOTEL:"
        )

        if hotel:
            print(
                " ",
                hotel.get(
                    "name"
                ),
                "|",
                hotel.get(
                    "price"
                ),
                "₽",
            )
        else:
            print(
                "  no hotel"
            )

        print()
        print(
            "INBOUND:"
        )

        print(
            " ",
            inbound.get(
                "mode"
            ),
            "|",
            inbound.get(
                "departure"
            ),
            "→",
            inbound.get(
                "arrival"
            ),
            "|",
            inbound.get(
                "price"
            ),
            "₽",
        )

        print()
        print(
            "TOTAL:",
            journey.get(
                "total_price"
            ),
            "₽",
        )

        print(
            "REPLACED:",
            ", ".join(
                candidate.get(
                    "replaced_components",
                    [],
                )
            ),
        )

        print(
            "PRESERVED:",
            ", ".join(
                candidate.get(
                    "preserved_components",
                    [],
                )
            ),
        )

        print(
            "SCORE:",
            candidate.get(
                "score"
            ),
        )

    print()
    print("=" * 68)

    if (
        data.get(
            "status"
        )
        == "candidates_found"
    ):
        print(
            "TRIP RESCUE END-TO-END: OK"
        )

    elif (
        data.get(
            "status"
        )
        == "no_candidates"
    ):
        print(
            "PIPELINE WORKED, "
            "BUT TUTU RETURNED NO VALID "
            "REPLACEMENT FOR THIS CONSTRAINT."
        )

    elif (
        data.get(
            "status"
        )
        == "no_change"
    ):
        print(
            "CURRENT JOURNEY STILL FITS "
            "THE UPDATED REQUEST."
        )

    print("=" * 68)

    print()
    print("RAW RESPONSE")
    print("=" * 68)

    print(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()