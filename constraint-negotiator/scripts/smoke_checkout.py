from __future__ import annotations

import json
import os
import sys

from datetime import (
    date,
    timedelta,
)

import httpx


BASE_URL = os.getenv(
    "CONSTRAINT_NEGOTIATOR_URL",
    "http://127.0.0.1:8010",
).rstrip("/")


def _title(
    value: str,
) -> None:
    print()
    print("=" * 72)
    print(value)
    print("=" * 72)


def _find_checkout_ref(
    response: dict,
) -> tuple[
    str,
    dict,
]:
    journeys = list(
        response.get(
            "journeys",
            [],
        )
    )

    for alternative in response.get(
        "alternatives",
        [],
    ):
        journey = alternative.get(
            "journey"
        )

        if isinstance(
            journey,
            dict,
        ):
            journeys.append(
                journey
            )

    for journey in journeys:
        if not isinstance(
            journey,
            dict,
        ):
            continue

        for component_name in (
            "outbound",
            "inbound",
            "hotel",
        ):
            component = journey.get(
                component_name
            )

            if not isinstance(
                component,
                dict,
            ):
                continue

            checkout_ref = (
                component.get(
                    "checkout_ref"
                )
            )

            if (
                isinstance(
                    checkout_ref,
                    dict,
                )
                and checkout_ref
            ):
                return (
                    component_name,
                    checkout_ref,
                )

    raise RuntimeError(
        "No checkout_ref was found "
        "in Negotiator response"
    )


def main() -> int:
    _title(
        "CONSTRAINT NEGOTIATOR — "
        "CHECKOUT E2E"
    )

    print(
        f"BASE_URL={BASE_URL}"
    )

    outbound = (
        date.today()
        + timedelta(
            days=7
        )
    )

    inbound = (
        outbound
        + timedelta(
            days=2
        )
    )

    print(
        "TRIP:",
        outbound.isoformat(),
        "->",
        inbound.isoformat(),
    )

    with httpx.Client(
        timeout=180.0,
    ) as client:
        health = client.get(
            BASE_URL
            + "/health"
        )

        print(
            "HEALTH HTTP:",
            health.status_code,
        )

        if (
            health.status_code
            != 200
        ):
            raise RuntimeError(
                "Health check failed"
            )

        print(
            "HEALTH: OK"
        )

        _title(
            "SEARCH FRESH OFFER"
        )

        search_response = (
            client.post(
                (
                    BASE_URL
                    + "/api/v1/"
                    "negotiator/from-spec"
                ),
                json={
                    "trip": {
                        "origin": (
                            "Москва"
                        ),
                        "destination": (
                            "Казань"
                        ),
                        "outbound_date": (
                            outbound.isoformat()
                        ),
                        "return_date": (
                            inbound.isoformat()
                        ),
                        "outbound_after": None,
                        "return_before": None,
                        "travelers": 1,
                        "budget": None,
                        "excluded_transport": [],
                        "preferred_transport": [],
                        "max_transfers": None,
                        "hard_constraints": [],
                    }
                },
            )
        )

        print(
            "SEARCH HTTP:",
            search_response.status_code,
        )

        if (
            search_response.status_code
            != 200
        ):
            print(
                search_response.text
            )

            raise RuntimeError(
                "Negotiator search failed"
            )

        search_data = (
            search_response.json()
        )

        print(
            "NEGOTIATION STATUS:",
            search_data.get(
                "status"
            ),
        )

        print(
            "JOURNEYS:",
            len(
                search_data.get(
                    "journeys",
                    [],
                )
            ),
        )

        print(
            "ALTERNATIVES:",
            len(
                search_data.get(
                    "alternatives",
                    [],
                )
            ),
        )

        (
            component_name,
            checkout_ref,
        ) = _find_checkout_ref(
            search_data
        )

        product_type = (
            checkout_ref.get(
                "product_type"
            )
            or checkout_ref.get(
                "transport"
            )
        )

        print(
            "CHECKOUT COMPONENT:",
            component_name,
        )

        print(
            "PRODUCT:",
            product_type,
        )

        print(
            "CHECKOUT REF KEYS:",
            sorted(
                checkout_ref.keys()
            ),
        )

        _title(
            "CREATE CHECKOUT LINK"
        )

        checkout_response = (
            client.post(
                (
                    BASE_URL
                    + "/api/v1/"
                    "negotiator/checkout"
                ),
                json={
                    "checkout_ref": (
                        checkout_ref
                    )
                },
            )
        )

        print(
            "CHECKOUT HTTP:",
            checkout_response.status_code,
        )

        if (
            checkout_response.status_code
            != 200
        ):
            print(
                checkout_response.text
            )

            raise RuntimeError(
                "Checkout endpoint failed"
            )

        checkout = (
            checkout_response.json()
        )

        print(
            "STATUS:",
            checkout[
                "status"
            ],
        )

        print(
            "KIND:",
            checkout[
                "kind"
            ],
        )

        print(
            "PROVIDER:",
            checkout[
                "provider"
            ],
        )

        print(
            "PRIMARY URL:",
            checkout[
                "primary_url"
            ],
        )

        assert (
            checkout[
                "provider"
            ]
            == "tutu"
        )

        assert (
            checkout[
                "primary_url"
            ].startswith(
                (
                    "http://",
                    "https://",
                )
            )
        )

        assert (
            checkout[
                "kind"
            ]
        )

        _title(
            "CHECKOUT RESPONSE"
        )

        print(
            json.dumps(
                checkout,
                ensure_ascii=False,
                indent=2,
            )
        )

    _title(
        "CHECKOUT E2E: OK"
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
            "CHECKOUT E2E: FAILED"
        )

        print(
            str(exc)
        )

        sys.exit(1)
