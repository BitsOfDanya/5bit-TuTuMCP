from __future__ import annotations

import json
import os
import sys

import httpx


BASE_URL = (
    os.getenv(
        "TRIP_RESCUE_URL",
        "http://127.0.0.1:8020",
    )
    .rstrip("/")
)


def fail(
    message: str,
) -> None:
    print()
    print(
        f"FAILED: {message}"
    )
    sys.exit(1)


def main() -> None:
    print(
        "=" * 72
    )

    print(
        "TRIP RESCUE — "
        "WHAT-IF SIMULATION"
    )

    print(
        "=" * 72
    )

    payload = {
        "current_trip": {
            "origin": "Москва",
            "destination": "Казань",
            "outbound_date": (
                "2026-08-21"
            ),
            "return_date": (
                "2026-08-23"
            ),
            "outbound_after": (
                "19:00:00"
            ),
            "return_before": (
                "22:00:00"
            ),
            "travelers": 2,
            "budget": 30000,
            "excluded_transport": [],
            "preferred_transport": [],
            "max_transfers": None,
            "hard_constraints": [],
        },

        "hypothetical_trip": {
            "origin": "Москва",
            "destination": "Казань",
            "outbound_date": (
                "2026-08-21"
            ),
            "return_date": (
                "2026-08-23"
            ),
            "outbound_after": (
                "19:00:00"
            ),
            "return_before": (
                "10:00:00"
            ),
            "travelers": 2,
            "budget": 30000,
            "excluded_transport": [],
            "preferred_transport": [],
            "max_transfers": None,
            "hard_constraints": [
                "return_before"
            ],
        },

        "current_journey": {
            "id": "current-journey",

            "total_price": 22703,

            "outbound": {
                "id": (
                    "current-outbound-bus"
                ),
                "mode": "bus",
                "origin": "Москва",
                "destination": "Казань",
                "departure": (
                    "2026-08-21"
                    "T22:45:00+03:00"
                ),
                "arrival": (
                    "2026-08-22"
                    "T08:45:00+03:00"
                ),
                "price": 5000,
                "duration_minutes": 600,
                "transfers": 0,
                "carrier": "Евротранс",
            },

            "inbound": {
                "id": (
                    "current-inbound-flight"
                ),
                "mode": "flight",
                "origin": "Казань",
                "destination": "Москва",
                "departure": (
                    "2026-08-23"
                    "T07:05:00+03:00"
                ),
                "arrival": (
                    "2026-08-23"
                    "T08:40:00+03:00"
                ),
                "price": 14428,
                "duration_minutes": 95,
                "transfers": 0,
            },

            "hotel": {
                "id": "current-hotel",
                "name": (
                    "Гостевой Дом "
                    "Мансарда"
                ),
                "price": 3275,
                "stars": 0,
                "rating": 7.03,
                "review_count": 48,
                "check_in": (
                    "2026-08-22"
                ),
                "check_out": (
                    "2026-08-23"
                ),
                "nights": 1,
            },
        },
    }

    url = (
        f"{BASE_URL}"
        "/api/v1/what-if/"
        "from-spec/public"
    )

    print()
    print(
        f"Calling: {url}"
    )

    response = httpx.post(
        url,
        json=payload,
        timeout=180.0,
    )

    print(
        f"HTTP: {response.status_code}"
    )

    if response.status_code >= 400:
        print(
            response.text
        )

        fail(
            "HTTP request failed"
        )

    data = response.json()

    print()
    print(
        "STATUS:",
        data.get("status"),
    )

    if (
        data.get("simulation")
        is not True
    ):
        fail(
            "response is not "
            "marked as simulation"
        )

    hypothetical = (
        data.get(
            "hypothetical_trip"
        )
        or {}
    )

    if (
        hypothetical.get(
            "return_before"
        )
        != "10:00:00"
    ):
        fail(
            "hypothetical deadline "
            "was not preserved"
        )

    print(
        "BASELINE VALID:",
        data.get(
            "baseline_valid"
        ),
    )

    candidates = (
        data.get("candidates")
        or []
    )

    print(
        "CANDIDATES:",
        len(candidates),
    )

    for candidate in candidates:
        print()
        print(
            "-" * 72
        )

        print(
            "RANK:",
            candidate.get(
                "rank"
            ),
        )

        journey = (
            candidate.get(
                "journey"
            )
            or {}
        )

        impact = (
            candidate.get(
                "impact"
            )
            or {}
        )

        print(
            "TOTAL:",
            journey.get(
                "total_price"
            ),
            "₽",
        )

        print(
            "PRICE DELTA:",
            impact.get(
                "price_delta"
            ),
            "₽",
        )

        print(
            "SAVINGS:",
            impact.get(
                "savings"
            ),
            "₽",
        )

        print(
            "ARRIVAL DELTA:",
            impact.get(
                "inbound_arrival_delta_minutes"
            ),
            "min",
        )

        print(
            "CHANGED:",
            ", ".join(
                impact.get(
                    "components_changed"
                )
                or []
            ),
        )

        inbound = (
            journey.get(
                "inbound"
            )
            or {}
        )

        print(
            "INBOUND:",
            inbound.get(
                "departure"
            ),
            "→",
            inbound.get(
                "arrival"
            ),
        )

    valid_statuses = {
        "alternatives_found",
        "no_alternatives",
    }

    if (
        data.get("status")
        not in valid_statuses
    ):
        fail(
            "unexpected What-if status"
        )

    print()
    print(
        "=" * 72
    )

    print(
        "WHAT-IF SIMULATION: OK"
    )

    print(
        "=" * 72
    )

    print()
    print(
        "RAW RESPONSE"
    )

    print(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()