from __future__ import annotations

import json
import sys

from datetime import datetime

import httpx


BASE_URL = (
    "http://127.0.0.1:8020"
)

URL = (
    f"{BASE_URL}"
    "/api/v1/rescue/from-text/public"
)


EXPECTED_DEADLINE = (
    datetime.fromisoformat(
        "2026-08-23T08:00:00+03:00"
    )
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

        "budget": 22_703,

        "excluded_transport": [],
        "preferred_transport": [],

        "max_transfers": None,

        "hard_constraints": [],
    },

    "current_journey": {
        "id": (
            "accepted-kazan-trip"
        ),

        "total_price": 22_703,

        "outbound": {
            "id": (
                "current-outbound-bus"
            ),

            "mode": "bus",

            "origin": (
                "Международный "
                "автовокзал Саларьево"
            ),

            "destination": (
                "Автовокзал Южный"
            ),

            "departure": (
                "2026-08-21"
                "T22:45:00+03:00"
            ),

            "arrival": (
                "2026-08-22"
                "T08:45:00+03:00"
            ),

            "price": 5_000,

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

            "price": 14_428,

            "duration_minutes": 95,

            "transfers": 0,

            "carrier": "Аэрофлот",
        },

        "hotel": {
            "id": (
                "current-hotel"
            ),

            "name": (
                "Гостевой Дом Мансарда"
            ),

            "price": 3_275,

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

    "message": (
        "Планы поменялись. "
        "23 августа мне теперь "
        "обязательно нужно быть "
        "в Москве до 8 утра, "
        "и желательно теперь "
        "уложиться максимум "
        "в 10 тысяч рублей."
    ),

    "reference_date": (
        "2026-08-19"
    ),
}


def fail(
    message: str,
    *,
    data: dict | None = None,
) -> None:
    print()
    print("=" * 72)
    print(
        "NEGOTIATION FALLBACK: FAILED"
    )
    print("=" * 72)

    print(
        message
    )

    if data is not None:
        print()

        print(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
            )
        )

    sys.exit(1)


def main() -> None:
    print()
    print("=" * 72)

    print(
        "TRIP RESCUE — "
        "NEGOTIATION FALLBACK"
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

    try:
        data = response.json()

    except Exception:
        fail(
            "Response is not valid JSON."
        )

    if response.status_code >= 400:
        fail(
            "HTTP request failed.",
            data=data,
        )

    status = (
        data.get(
            "status"
        )
    )

    print(
        "STATUS:",
        status
    )

    if (
        status
        != "negotiation_required"
    ):
        fail(
            "Expected "
            "'negotiation_required'.",
            data=data,
        )

    updated_trip = (
        data.get(
            "updated_trip"
        )
        or {}
    )

    hard_constraints = set(
        updated_trip.get(
            "hard_constraints"
        )
        or []
    )

    print()
    print("UPDATED HARD CONSTRAINTS")
    print("-" * 72)

    print(
        sorted(
            hard_constraints
        )
    )

    # ---------------------------------------------------------
    # Critical semantic assertion #1:
    # return deadline MUST be hard.
    # ---------------------------------------------------------

    if (
        "return_before"
        not in hard_constraints
    ):
        fail(
            "return_before MUST be hard "
            "for wording 'обязательно "
            "нужно быть до 8 утра'.",
            data=data,
        )

    # ---------------------------------------------------------
    # Critical semantic assertion #2:
    # budget MUST remain soft.
    # ---------------------------------------------------------

    if (
        "budget"
        in hard_constraints
    ):
        fail(
            "budget MUST stay soft "
            "because wording is "
            "'желательно уложиться'.",
            data=data,
        )

    if (
        updated_trip.get(
            "return_before"
        )
        != "08:00:00"
    ):
        fail(
            "Updated return_before "
            "must equal 08:00:00.",
            data=data,
        )

    if (
        updated_trip.get(
            "budget"
        )
        != 10_000
    ):
        fail(
            "Updated soft budget "
            "must equal 10000.",
            data=data,
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
        len(candidates)
    )

    if not candidates:
        fail(
            "Expected at least one "
            "negotiation candidate.",
            data=data,
        )

    found_budget_relaxation = (
        False
    )

    for index, candidate in enumerate(
        candidates,
        start=1,
    ):
        print()
        print(
            f"--- NEGOTIATION #{index} ---"
        )

        summary = (
            candidate.get(
                "summary"
            )
            or {}
        )

        print(
            summary.get(
                "headline"
            )
        )

        print(
            summary.get(
                "explanation"
            )
        )

        exact = (
            candidate.get(
                "exact"
            )
        )

        print(
            "EXACT:",
            exact
        )

        if exact is not False:
            fail(
                "Negotiation candidate "
                "must have exact=false.",
                data=candidate,
            )

        journey = (
            candidate.get(
                "journey"
            )
            or {}
        )

        total = (
            journey.get(
                "total_price"
            )
        )

        print(
            "TOTAL:",
            total
        )

        relaxations = (
            candidate.get(
                "relaxations"
            )
            or []
        )

        print(
            "RELAXATIONS:"
        )

        for relaxation in (
            relaxations
        ):
            field = (
                relaxation.get(
                    "field"
                )
            )

            description = (
                relaxation.get(
                    "description"
                )
            )

            print(
                " ~",
                field,
                ":",
                description,
            )

            if field == "budget":
                found_budget_relaxation = (
                    True
                )

            # -------------------------------------------------
            # Critical assertion #3:
            # hard return deadline can NEVER be negotiated.
            # -------------------------------------------------

            if (
                field
                == "return_before"
            ):
                fail(
                    "Candidate illegally "
                    "relaxes HARD "
                    "return_before.",
                    data=candidate,
                )

        suggested_trip = (
            candidate.get(
                "suggested_trip"
            )
        )

        if not suggested_trip:
            fail(
                "Negotiation candidate "
                "must contain "
                "suggested_trip.",
                data=candidate,
            )

        suggested_hard = set(
            suggested_trip.get(
                "hard_constraints"
            )
            or []
        )

        # -----------------------------------------------------
        # Critical assertion #4:
        # hard constraint must survive into suggestion.
        # -----------------------------------------------------

        if (
            "return_before"
            not in suggested_hard
        ):
            fail(
                "suggested_trip lost "
                "hard return_before.",
                data=candidate,
            )

        if (
            suggested_trip.get(
                "return_before"
            )
            != "08:00:00"
        ):
            fail(
                "suggested_trip changed "
                "hard return_before.",
                data=candidate,
            )

        inbound = (
            journey.get(
                "inbound"
            )
            or {}
        )

        arrival_raw = (
            inbound.get(
                "arrival"
            )
        )

        if not arrival_raw:
            fail(
                "Candidate has no "
                "inbound arrival.",
                data=candidate,
            )

        arrival = (
            datetime.fromisoformat(
                arrival_raw
            )
        )

        # -----------------------------------------------------
        # Critical assertion #5:
        # real route must actually satisfy deadline.
        # -----------------------------------------------------

        if (
            arrival
            > EXPECTED_DEADLINE
        ):
            fail(
                "Candidate arrives after "
                "the HARD 08:00 deadline.",
                data=candidate,
            )

        print(
            "INBOUND ARRIVAL:",
            arrival.isoformat(),
            "✓",
        )

        print(
            "HARD RETURN:",
            "08:00",
            "✓",
        )

        print(
            "SUGGESTED TRIP:"
        )

        print(
            json.dumps(
                suggested_trip,
                ensure_ascii=False,
                indent=2,
            )
        )

    if not found_budget_relaxation:
        fail(
            "Expected at least one "
            "budget relaxation.",
            data=data,
        )

    print()
    print("=" * 72)

    print(
        "HARD CONSTRAINT CHECK: OK"
    )

    print(
        "SOFT BUDGET CHECK: OK"
    )

    print(
        "ALL ROUTES ARRIVE <= 08:00: OK"
    )

    print(
        "NEGOTIATION FALLBACK: OK"
    )

    print("=" * 72)


if __name__ == "__main__":
    main()