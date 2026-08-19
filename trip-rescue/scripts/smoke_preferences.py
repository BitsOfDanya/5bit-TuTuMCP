from __future__ import annotations

import json
import sys

import httpx


BASE_URL = "http://127.0.0.1:8020"

PROFILE_ID = "demo-price-lover"


FEEDBACK_URL = (
    f"{BASE_URL}"
    "/api/v1/preferences/feedback"
)

PROFILE_URL = (
    f"{BASE_URL}"
    f"/api/v1/preferences/{PROFILE_ID}"
)

RERANK_URL = (
    f"{BASE_URL}"
    "/api/v1/preferences/rerank"
)

RESCUE_URL = (
    f"{BASE_URL}"
    "/api/v1/rescue/from-text/public"
)


def candidate(
    *,
    candidate_id: str,
    price: int,
    duration_minutes: int,
) -> dict:
    half = price // 2

    return {
        "id": candidate_id,
        "total_price": price,

        "outbound": {
            "mode": "bus",
            "origin": "Москва",
            "destination": "Казань",
            "departure": (
                "2026-08-21T20:00:00+03:00"
            ),
            "arrival": (
                "2026-08-21T23:00:00+03:00"
            ),
            "price": half,
            "duration_minutes": (
                duration_minutes
            ),
            "transfers": 0,
        },

        "inbound": {
            "mode": "bus",
            "origin": "Казань",
            "destination": "Москва",
            "departure": (
                "2026-08-23T04:00:00+03:00"
            ),
            "arrival": (
                "2026-08-23T07:00:00+03:00"
            ),
            "price": (
                price - half
            ),
            "duration_minutes": (
                duration_minutes
            ),
            "transfers": 0,
        },

        "hotel": None,
    }


CHEAP = candidate(
    candidate_id="cheap",
    price=10_000,
    duration_minutes=600,
)

MID = candidate(
    candidate_id="mid",
    price=20_000,
    duration_minutes=400,
)

EXPENSIVE = candidate(
    candidate_id="expensive",
    price=30_000,
    duration_minutes=150,
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
}


def main() -> None:
    print()
    print("=" * 72)
    print(
        "TRIP RESCUE — "
        "PREFERENCE LEARNING SMOKE"
    )
    print("=" * 72)

    with httpx.Client(
        timeout=180.0
    ) as client:

        # -----------------------------------------------------
        # RESET PROFILE
        # -----------------------------------------------------

        client.delete(
            PROFILE_URL
        )

        print()
        print("PROFILE RESET")
        print("-" * 72)

        # -----------------------------------------------------
        # TEACH:
        # repeatedly choose cheap option
        # -----------------------------------------------------

        print()
        print("LEARNING")
        print("-" * 72)

        shown_candidates = [
            CHEAP,
            MID,
            EXPENSIVE,
        ]

        for interaction in range(
            1,
            7,
        ):
            response = client.post(
                FEEDBACK_URL,
                json={
                    "profile_id": (
                        PROFILE_ID
                    ),
                    "action": "choose",
                    "candidate": CHEAP,
                    "shown_candidates": (
                        shown_candidates
                    ),
                },
            )

            if response.status_code >= 400:
                print(
                    "FEEDBACK FAILED:"
                )

                print(
                    response.text
                )

                sys.exit(1)

            data = (
                response.json()
            )

            profile = (
                data["profile"]
            )

            print(
                f"#{interaction}",
                "price_weight=",
                profile[
                    "weights"
                ][
                    "price"
                ],
                "interactions=",
                profile[
                    "interactions"
                ],
            )

        # -----------------------------------------------------
        # LOAD PROFILE
        # -----------------------------------------------------

        response = client.get(
            PROFILE_URL
        )

        if response.status_code >= 400:
            print(
                "PROFILE LOAD FAILED"
            )

            print(
                response.text
            )

            sys.exit(1)

        profile = (
            response.json()
        )

        print()
        print("LEARNED PROFILE")
        print("-" * 72)

        print(
            json.dumps(
                profile,
                ensure_ascii=False,
                indent=2,
            )
        )

        price_weight = (
            profile[
                "weights"
            ][
                "price"
            ]
        )

        if price_weight <= 0:
            print()
            print(
                "ERROR: "
                "price preference "
                "was not learned"
            )

            sys.exit(1)

        # -----------------------------------------------------
        # CONTROLLED RERANK TEST
        # -----------------------------------------------------

        print()
        print("CONTROLLED RERANK")
        print("-" * 72)

        response = client.post(
            RERANK_URL,
            json={
                "profile_id": (
                    PROFILE_ID
                ),
                # Deliberately expensive-first.
                "candidates": [
                    EXPENSIVE,
                    MID,
                    CHEAP,
                ],
            },
        )

        if response.status_code >= 400:
            print(
                "RERANK FAILED"
            )

            print(
                response.text
            )

            sys.exit(1)

        rerank = (
            response.json()
        )

        for item in (
            rerank[
                "items"
            ]
        ):
            print(
                item[
                    "candidate_id"
                ],
                "|",
                "before=",
                item[
                    "rank_before"
                ],
                "|",
                "after=",
                item[
                    "rank_after"
                ],
                "|",
                "score=",
                item[
                    "preference_score"
                ],
            )

        reranked_ids = [
            item[
                "candidate_id"
            ]
            for item
            in rerank[
                "items"
            ]
        ]

        if (
            not reranked_ids
            or reranked_ids[0]
            != "cheap"
        ):
            print()
            print(
                "ERROR: "
                "personalized reranker "
                "did not promote "
                "cheap candidate"
            )

            sys.exit(1)

        print()
        print(
            "CONTROLLED RERANK: OK"
        )

        # -----------------------------------------------------
        # REAL TRIP RESCUE
        # -----------------------------------------------------

        print()
        print("=" * 72)
        print(
            "REAL PERSONALIZED "
            "TRIP RESCUE"
        )
        print("=" * 72)

        rescue_payload = {
            "current_trip": (
                CURRENT_TRIP
            ),

            "current_journey": (
                CURRENT_JOURNEY
            ),

            "message": (
                "Планы поменялись. "
                "23 августа мне теперь "
                "обязательно нужно быть "
                "в Москве до 8 утра."
            ),

            "reference_date": (
                "2026-08-19"
            ),

            "preference_profile_id": (
                PROFILE_ID
            ),
        }

        response = client.post(
            RESCUE_URL,
            json=rescue_payload,
        )

        print(
            "HTTP:",
            response.status_code
        )

        if response.status_code >= 400:
            print(
                response.text
            )

            sys.exit(1)

        rescue = (
            response.json()
        )

        print(
            "STATUS:",
            rescue.get(
                "status"
            ),
        )

        personalization = (
            rescue.get(
                "personalization"
            )
        )

        print()
        print("PERSONALIZATION")
        print("-" * 72)

        print(
            json.dumps(
                personalization,
                ensure_ascii=False,
                indent=2,
            )
        )

        if (
            not personalization
            or not personalization.get(
                "applied"
            )
        ):
            print()
            print(
                "ERROR: "
                "personalization "
                "was not applied"
            )

            sys.exit(1)

        candidates = (
            rescue.get(
                "candidates"
            )
            or []
        )

        if not candidates:
            print()
            print(
                "ERROR: "
                "no Rescue candidates"
            )

            sys.exit(1)

        print()
        print("PERSONALIZED CANDIDATES")
        print("-" * 72)

        for index, item in enumerate(
            candidates,
            start=1,
        ):
            personal = (
                item.get(
                    "personalization"
                )
                or {}
            )

            journey = (
                item.get(
                    "journey"
                )
                or {}
            )

            print()
            print(
                f"#{index}"
            )

            print(
                "TOTAL:",
                journey.get(
                    "total_price"
                ),
                "₽",
            )

            print(
                "BASE SCORE:",
                item.get(
                    "score"
                ),
            )

            print(
                "PREFERENCE SCORE:",
                personal.get(
                    "preference_score"
                ),
            )

            print(
                "PERSONALIZED SCORE:",
                personal.get(
                    "personalized_score"
                ),
            )

            print(
                "RANK:",
                personal.get(
                    "rank_before"
                ),
                "→",
                personal.get(
                    "rank_after"
                ),
            )

            reasons = (
                personal.get(
                    "reasons"
                )
                or []
            )

            for reason in reasons:
                print(
                    "  •",
                    reason
                )

        # -----------------------------------------------------
        # FINAL CHECK
        # -----------------------------------------------------

        has_metadata = all(
            candidate.get(
                "personalization"
            )
            is not None
            for candidate
            in candidates
        )

        if not has_metadata:
            print()
            print(
                "ERROR: candidate "
                "personalization metadata "
                "missing"
            )

            sys.exit(1)

        print()
        print("=" * 72)
        print(
            "PREFERENCE LEARNING "
            "END-TO-END: OK"
        )
        print("=" * 72)


if __name__ == "__main__":
    main()