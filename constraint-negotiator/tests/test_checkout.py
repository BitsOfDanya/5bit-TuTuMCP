from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import (
    TestClient,
)

import app.api.checkout as checkout_api

from app.tutu.client import (
    TutuMCPError,
)


class FakeTutuClient:
    response: dict[
        str,
        Any,
    ] = {}

    error: (
        Exception
        | None
    ) = None

    calls: list[
        tuple[
            str,
            dict[str, Any],
        ]
    ] = []

    async def call_tool(
        self,
        *,
        name: str,
        arguments: dict[
            str,
            Any,
        ],
    ) -> dict[str, Any]:
        self.__class__.calls.append(
            (
                name,
                arguments,
            )
        )

        if (
            self.__class__.error
            is not None
        ):
            raise (
                self.__class__.error
            )

        return dict(
            self.__class__.response
        )


def _client(
    monkeypatch,
) -> TestClient:
    FakeTutuClient.response = {}
    FakeTutuClient.error = None
    FakeTutuClient.calls = []

    monkeypatch.setattr(
        checkout_api,
        "TutuMCPClient",
        FakeTutuClient,
    )

    app = FastAPI()

    app.include_router(
        checkout_api.router
    )

    return TestClient(app)


def test_checkout_forwards_ref_verbatim(
    monkeypatch,
) -> None:
    client = _client(
        monkeypatch
    )

    opaque_offer_hash = (
        '{"Price":12886,'
        '"OriginalHash":"abc"}'
    )

    checkout_ref = {
        "transport": "avia",
        "search_results_url": (
            "https://avia.tutu.ru/"
            "search"
        ),
        "offer_hash": (
            opaque_offer_hash
        ),
        "departure_geo_city_id": (
            2656873
        ),
        "arrival_geo_city_id": (
            2657260
        ),
        "departure_at": (
            "2026-08-21"
            "T21:40:00+03:00"
        ),
        "service_class": (
            "ECONOMIC"
        ),
        "passengers_full": 2,
        "passengers_child": 0,
        "passengers_infant": 0,
    }

    FakeTutuClient.response = {
        "kind": "deeplink",
        "checkout_url": (
            "https://mtp-deeplink."
            "tutu.ru/exact-link"
        ),
        "search_results_url": (
            "https://avia.tutu.ru/"
            "search"
        ),
    }

    response = client.post(
        (
            "/api/v1/negotiator/"
            "checkout"
        ),
        json={
            "checkout_ref": (
                checkout_ref
            )
        },
    )

    assert (
        response.status_code
        == 200
    )

    assert (
        FakeTutuClient.calls
        == [
            (
                "create_checkout_link",
                checkout_ref,
            )
        ]
    )

    data = response.json()

    assert (
        data["status"]
        == "ready"
    )

    assert (
        data["kind"]
        == "deeplink"
    )

    assert (
        data["primary_url"]
        == data[
            "checkout_url"
        ]
    )


def test_search_redirect_uses_search_page(
    monkeypatch,
) -> None:
    client = _client(
        monkeypatch
    )

    FakeTutuClient.response = {
        "kind": (
            "search_redirect"
        ),
        "checkout_url": (
            "https://example.test/"
            "fallback-deeplink"
        ),
        "search_results_url": (
            "https://avia.tutu.ru/"
            "real-search"
        ),
        "fallback_note": (
            "Offer requires search "
            "fallback"
        ),
    }

    response = client.post(
        (
            "/api/v1/negotiator/"
            "checkout"
        ),
        json={
            "checkout_ref": {
                "transport": (
                    "avia"
                ),
                "search_results_url": (
                    "https://avia.tutu.ru/"
                    "real-search"
                ),
            }
        },
    )

    assert (
        response.status_code
        == 200
    )

    data = response.json()

    assert (
        data["status"]
        == "fallback"
    )

    assert (
        data["primary_url"]
        == (
            "https://avia.tutu.ru/"
            "real-search"
        )
    )


def test_bus_deeplink_is_ready(
    monkeypatch,
) -> None:
    client = _client(
        monkeypatch
    )

    FakeTutuClient.response = {
        "kind": "deeplink",
        "checkout_url": (
            "https://mtp-deeplink."
            "tutu.ru/bus"
        ),
    }

    response = client.post(
        (
            "/api/v1/negotiator/"
            "checkout"
        ),
        json={
            "checkout_ref": {
                "transport": "bus",
                "offer_hash": "abc",
                "departure_geo_city_id": 1,
                "arrival_geo_city_id": 2,
                "departure_at": (
                    "2026-08-21"
                    "T22:45:00+03:00"
                ),
            }
        },
    )

    assert (
        response.status_code
        == 200
    )

    data = response.json()

    assert (
        data["kind"]
        == "deeplink"
    )

    assert (
        data["status"]
        == "ready"
    )


def test_missing_product_is_rejected(
    monkeypatch,
) -> None:
    client = _client(
        monkeypatch
    )

    response = client.post(
        (
            "/api/v1/negotiator/"
            "checkout"
        ),
        json={
            "checkout_ref": {
                "offer_hash": "abc"
            }
        },
    )

    assert (
        response.status_code
        == 422
    )

    assert (
        FakeTutuClient.calls
        == []
    )


def test_unknown_product_is_rejected(
    monkeypatch,
) -> None:
    client = _client(
        monkeypatch
    )

    response = client.post(
        (
            "/api/v1/negotiator/"
            "checkout"
        ),
        json={
            "checkout_ref": {
                "transport": (
                    "spaceship"
                )
            }
        },
    )

    assert (
        response.status_code
        == 422
    )

    assert (
        FakeTutuClient.calls
        == []
    )


def test_mcp_tool_error_becomes_502(
    monkeypatch,
) -> None:
    client = _client(
        monkeypatch
    )

    FakeTutuClient.error = (
        TutuMCPError(
            "failed"
        )
    )

    response = client.post(
        (
            "/api/v1/negotiator/"
            "checkout"
        ),
        json={
            "checkout_ref": {
                "transport": "avia"
            }
        },
    )

    assert (
        response.status_code
        == 502
    )


def test_transport_error_becomes_503(
    monkeypatch,
) -> None:
    client = _client(
        monkeypatch
    )

    FakeTutuClient.error = (
        RuntimeError(
            "network unavailable"
        )
    )

    response = client.post(
        (
            "/api/v1/negotiator/"
            "checkout"
        ),
        json={
            "checkout_ref": {
                "transport": "bus"
            }
        },
    )

    assert (
        response.status_code
        == 503
    )


def test_missing_url_from_mcp_is_502(
    monkeypatch,
) -> None:
    client = _client(
        monkeypatch
    )

    FakeTutuClient.response = {
        "kind": "deeplink"
    }

    response = client.post(
        (
            "/api/v1/negotiator/"
            "checkout"
        ),
        json={
            "checkout_ref": {
                "transport": "avia"
            }
        },
    )

    assert (
        response.status_code
        == 502
    )