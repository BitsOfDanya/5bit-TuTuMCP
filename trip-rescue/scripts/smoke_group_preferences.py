from __future__ import annotations

import json
import os
import sys
from typing import Any

import httpx


BASE_URL = os.getenv(
    "TRIP_RESCUE_URL",
    "http://127.0.0.1:8020",
).rstrip("/")


PROFILE_A = "demo-group-danya"
PROFILE_B = "demo-group-misha"

GROUP_ID = "demo-weekend-kazan"


def _print_title(
    value: str,
) -> None:
    print()
    print("=" * 72)
    print(value)
    print("=" * 72)


def _print_json(
    value: Any,
) -> None:
    print(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
        )
    )


def _journey(
    *,
    journey_id: str,
    mode: str,
    total_price: int,
    duration_minutes: int,
) -> dict:
    outbound_duration = (
        duration_minutes
        // 2
    )

    inbound_duration = (
        duration_minutes
        - outbound_duration
    )

    outbound_price = (
        total_price
        // 2
    )

    inbound_price = (
        total_price
        - outbound_price
    )

    return {
        "id": journey_id,
        "total_price": total_price,
        "outbound": {
            "id": (
                f"{journey_id}-out"
            ),
            "mode": mode,
            "origin": "Москва",
            "destination": "Казань",
            "departure": (
                "2026-08-21"
                "T20:00:00+03:00"
            ),
            "arrival": (
                "2026-08-21"
                "T22:00:00+03:00"
            ),
            "price": outbound_price,
            "duration_minutes": (
                outbound_duration
            ),
            "transfers": 0,
        },
        "inbound": {
            "id": (
                f"{journey_id}-in"
            ),
            "mode": mode,
            "origin": "Казань",
            "destination": "Москва",
            "departure": (
                "2026-08-23"
                "T18:00:00+03:00"
            ),
            "arrival": (
                "2026-08-23"
                "T20:00:00+03:00"
            ),
            "price": inbound_price,
            "duration_minutes": (
                inbound_duration
            ),
            "transfers": 0,
        },
        "hotel": None,
    }


def _cold_start_choices_price() -> list[
    dict
]:
    return [
        {
            "question_id": (
                "price-vs-speed"
            ),
            "selected_option_id": (
                "price-vs-speed:cheap"
            ),
        },
        {
            "question_id": (
                "direct-vs-cheaper"
            ),
            "selected_option_id": (
                "direct-vs-cheaper:"
                "transfer"
            ),
        },
        {
            "question_id": (
                "hotel-quality-vs-price"
            ),
            "selected_option_id": (
                "hotel-quality-vs-price:"
                "budget"
            ),
        },
        {
            "question_id": (
                "arrival-time-vs-price"
            ),
            "selected_option_id": (
                "arrival-time-vs-price:"
                "cheaper"
            ),
        },
    ]


def _cold_start_choices_speed() -> list[
    dict
]:
    return [
        {
            "question_id": (
                "price-vs-speed"
            ),
            "selected_option_id": (
                "price-vs-speed:fast"
            ),
        },
        {
            "question_id": (
                "direct-vs-cheaper"
            ),
            "selected_option_id": (
                "direct-vs-cheaper:"
                "direct"
            ),
        },
        {
            "question_id": (
                "arrival-time-vs-price"
            ),
            "selected_option_id": (
                "arrival-time-vs-price:"
                "earlier"
            ),
        },
        {
            "question_id": (
                "flight-direct-vs-connection"
            ),
            "selected_option_id": (
                "flight-direct-vs-connection:"
                "direct"
            ),
        },
    ]


def _post(
    *,
    client: httpx.Client,
    path: str,
    payload: dict,
) -> dict:
    response = client.post(
        (
            BASE_URL
            + path
        ),
        json=payload,
    )

    print(
        f"POST {path}"
    )

    print(
        f"HTTP {response.status_code}"
    )

    if (
        response.status_code
        >= 400
    ):
        print(
            response.text
        )

        raise RuntimeError(
            f"{path} failed"
        )

    return response.json()


def _delete_profile(
    *,
    client: httpx.Client,
    profile_id: str,
) -> None:
    client.delete(
        (
            BASE_URL
            + "/api/v1/preferences/"
            + profile_id
        )
    )


def main() -> int:
    _print_title(
        "GROUP PREFERENCES — "
        "END-TO-END SMOKE"
    )

    print(
        f"BASE_URL={BASE_URL}"
    )

    with httpx.Client(
        timeout=30.0
    ) as client:
        health = client.get(
            BASE_URL
            + "/health"
        )

        if (
            health.status_code
            != 200
        ):
            print(
                "HEALTH: FAILED"
            )

            return 1

        print(
            "HEALTH: OK"
        )

        # -----------------------------------------------------
        # Clean previous smoke state
        # -----------------------------------------------------

        _delete_profile(
            client=client,
            profile_id=PROFILE_A,
        )

        _delete_profile(
            client=client,
            profile_id=PROFILE_B,
        )

        # -----------------------------------------------------
        # Member A: price-sensitive
        # -----------------------------------------------------

        _print_title(
            "CREATE MEMBER A"
        )

        member_a = _post(
            client=client,
            path=(
                "/api/v1/preferences/"
                "cold-start/complete"
            ),
            payload={
                "profile_id": PROFILE_A,
                "choices": (
                    _cold_start_choices_price()
                ),
            },
        )

        _print_json(
            {
                "profile_id": (
                    member_a[
                        "profile"
                    ][
                        "profile_id"
                    ]
                ),
                "weights": (
                    member_a[
                        "profile"
                    ][
                        "weights"
                    ]
                ),
                "transport_affinity": (
                    member_a[
                        "profile"
                    ][
                        "transport_affinity"
                    ]
                ),
            }
        )

        # -----------------------------------------------------
        # Member B: speed / direct-sensitive
        # -----------------------------------------------------

        _print_title(
            "CREATE MEMBER B"
        )

        member_b = _post(
            client=client,
            path=(
                "/api/v1/preferences/"
                "cold-start/complete"
            ),
            payload={
                "profile_id": PROFILE_B,
                "choices": (
                    _cold_start_choices_speed()
                ),
            },
        )

        _print_json(
            {
                "profile_id": (
                    member_b[
                        "profile"
                    ][
                        "profile_id"
                    ]
                ),
                "weights": (
                    member_b[
                        "profile"
                    ][
                        "weights"
                    ]
                ),
                "transport_affinity": (
                    member_b[
                        "profile"
                    ][
                        "transport_affinity"
                    ]
                ),
            }
        )

        # -----------------------------------------------------
        # Build virtual group profile
        # -----------------------------------------------------

        _print_title(
            "GROUP PROFILE"
        )

        group = _post(
            client=client,
            path=(
                "/api/v1/preferences/"
                "group/profile"
            ),
            payload={
                "group_id": GROUP_ID,
                "profile_ids": [
                    PROFILE_A,
                    PROFILE_B,
                ],
            },
        )

        assert (
            group["group_id"]
            == GROUP_ID
        )

        assert (
            group["member_count"]
            == 2
        )

        assert (
            group["profile"][
                "profile_id"
            ]
            == (
                "group:"
                + GROUP_ID
            )
        )

        assert (
            0.0
            <= group[
                "consensus_score"
            ]
            <= 1.0
        )

        _print_json(
            {
                "group_id": (
                    group["group_id"]
                ),
                "member_count": (
                    group[
                        "member_count"
                    ]
                ),
                "weights": (
                    group[
                        "profile"
                    ][
                        "weights"
                    ]
                ),
                "transport_affinity": (
                    group[
                        "profile"
                    ][
                        "transport_affinity"
                    ]
                ),
                "consensus_score": (
                    group[
                        "consensus_score"
                    ]
                ),
                "conflicts": (
                    group["conflicts"]
                ),
                "highlights": (
                    group["highlights"]
                ),
            }
        )

        # -----------------------------------------------------
        # Group rerank
        # -----------------------------------------------------

        _print_title(
            "GROUP RERANK"
        )

        reranked = _post(
            client=client,
            path=(
                "/api/v1/preferences/"
                "group/rerank"
            ),
            payload={
                "group_id": GROUP_ID,
                "profile_ids": [
                    PROFILE_A,
                    PROFILE_B,
                ],
                "candidates": [
                    _journey(
                        journey_id=(
                            "cheap-bus"
                        ),
                        mode="bus",
                        total_price=8_000,
                        duration_minutes=(
                            1_000
                        ),
                    ),
                    _journey(
                        journey_id=(
                            "balanced-train"
                        ),
                        mode="train",
                        total_price=11_000,
                        duration_minutes=(
                            600
                        ),
                    ),
                    _journey(
                        journey_id=(
                            "fast-flight"
                        ),
                        mode="flight",
                        total_price=15_000,
                        duration_minutes=(
                            220
                        ),
                    ),
                ],
            },
        )

        assert (
            reranked["group"][
                "member_count"
            ]
            == 2
        )

        assert (
            len(
                reranked["items"]
            )
            == 3
        )

        for item in (
            reranked["items"]
        ):
            print()
            print(
                (
                    f"#{item['rank_after']} "
                    f"{item['candidate_id']}"
                )
            )

            print(
                (
                    "rank: "
                    f"{item['rank_before']}"
                    " -> "
                    f"{item['rank_after']}"
                )
            )

            print(
                (
                    "preference_score: "
                    f"{item['preference_score']}"
                )
            )

            for reason in (
                item["reasons"]
            ):
                print(
                    f"  • {reason}"
                )

        # -----------------------------------------------------
        # Virtual group profile must NOT persist
        # -----------------------------------------------------

        virtual = client.get(
            (
                BASE_URL
                + "/api/v1/preferences/"
                + "group:"
                + GROUP_ID
            )
        )

        assert (
            virtual.status_code
            == 404
        )

        print()
        print(
            "VIRTUAL PROFILE: "
            "NOT PERSISTED — OK"
        )

        # -----------------------------------------------------
        # Individual profiles remain alive
        # -----------------------------------------------------

        member_check = (
            client.get(
                (
                    BASE_URL
                    + "/api/v1/preferences/"
                    + PROFILE_A
                )
            )
        )

        assert (
            member_check.status_code
            == 200
        )

        print(
            "MEMBER PROFILE: "
            "PRESERVED — OK"
        )

    _print_title(
        "GROUP PREFERENCES "
        "END-TO-END: OK"
    )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(
            main()
        )

    except (
        AssertionError,
        RuntimeError,
        httpx.HTTPError,
    ) as exc:
        print()
        print(
            "GROUP PREFERENCES "
            "END-TO-END: FAILED"
        )

        print(
            str(exc)
        )

        sys.exit(1)