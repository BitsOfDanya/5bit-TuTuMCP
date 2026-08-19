from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import (
    TestClient,
)

import app.api.preferences as preferences_api

from app.preferences.group_service import (
    GroupPreferenceService,
)
from app.preferences.models import (
    PreferenceProfile,
    PreferenceWeights,
)
from app.preferences.store import (
    PreferenceStore,
)


def _journey(
    journey_id: str,
    *,
    price: int,
    mode: str,
    duration_minutes: int,
) -> dict:
    return {
        "id": journey_id,
        "total_price": price,
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
            "price": (
                price // 2
            ),
            "duration_minutes": (
                duration_minutes
                // 2
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
            "price": (
                price
                - price // 2
            ),
            "duration_minutes": (
                duration_minutes
                - duration_minutes // 2
            ),
            "transfers": 0,
        },
        "hotel": None,
    }


def _client(
    monkeypatch,
) -> tuple[
    TestClient,
    PreferenceStore,
]:
    store = PreferenceStore()

    store.save(
        PreferenceProfile(
            profile_id="danya",
            interactions=4,
            weights=(
                PreferenceWeights(
                    price=1.7,
                    duration=0.2,
                )
            ),
            transport_affinity={
                "bus": 0.8,
                "flight": -0.3,
            },
        )
    )

    store.save(
        PreferenceProfile(
            profile_id="misha",
            interactions=6,
            weights=(
                PreferenceWeights(
                    price=0.4,
                    duration=1.5,
                )
            ),
            transport_affinity={
                "bus": -0.4,
                "flight": 1.0,
            },
        )
    )

    service = (
        GroupPreferenceService(
            store=store
        )
    )

    monkeypatch.setattr(
        preferences_api,
        "get_group_preference_service",
        lambda: service,
    )

    monkeypatch.setattr(
        preferences_api,
        "get_preference_store",
        lambda: store,
    )

    app = FastAPI()

    app.include_router(
        preferences_api.router
    )

    return (
        TestClient(app),
        store,
    )


def test_group_profile_endpoint(
    monkeypatch,
) -> None:
    client, store = _client(
        monkeypatch
    )

    count_before = (
        store.count()
    )

    response = client.post(
        (
            "/api/v1/preferences/"
            "group/profile"
        ),
        json={
            "group_id": (
                "weekend-kazan"
            ),
            "profile_ids": [
                "danya",
                "misha",
            ],
        },
    )

    assert (
        response.status_code
        == 200
    )

    data = response.json()

    assert (
        data["group_id"]
        == "weekend-kazan"
    )

    assert (
        data["member_count"]
        == 2
    )

    assert (
        data["profile"][
            "profile_id"
        ]
        == "group:weekend-kazan"
    )

    assert (
        0.0
        <= data[
            "consensus_score"
        ]
        <= 1.0
    )

    # Virtual group profile must not
    # appear in the persistent store.
    assert (
        store.count()
        == count_before
    )

    assert (
        store.get(
            "group:weekend-kazan"
        )
        is None
    )


def test_group_profile_reports_conflicts(
    monkeypatch,
) -> None:
    client, _ = _client(
        monkeypatch
    )

    response = client.post(
        (
            "/api/v1/preferences/"
            "group/profile"
        ),
        json={
            "group_id": "friends",
            "profile_ids": [
                "danya",
                "misha",
            ],
        },
    )

    assert (
        response.status_code
        == 200
    )

    data = response.json()

    assert (
        data["conflicts"]
    )


def test_group_rerank_endpoint(
    monkeypatch,
) -> None:
    client, _ = _client(
        monkeypatch
    )

    response = client.post(
        (
            "/api/v1/preferences/"
            "group/rerank"
        ),
        json={
            "group_id": "friends",
            "profile_ids": [
                "danya",
                "misha",
            ],
            "candidates": [
                _journey(
                    "cheap-bus",
                    price=8_000,
                    mode="bus",
                    duration_minutes=(
                        1_000
                    ),
                ),
                _journey(
                    "fast-flight",
                    price=15_000,
                    mode="flight",
                    duration_minutes=(
                        220
                    ),
                ),
            ],
        },
    )

    assert (
        response.status_code
        == 200
    )

    data = response.json()

    assert (
        data["group"][
            "member_count"
        ]
        == 2
    )

    assert (
        len(
            data["items"]
        )
        == 2
    )

    candidate_ids = {
        item["candidate_id"]
        for item
        in data["items"]
    }

    assert candidate_ids == {
        "cheap-bus",
        "fast-flight",
    }


def test_missing_member_returns_404(
    monkeypatch,
) -> None:
    client, _ = _client(
        monkeypatch
    )

    response = client.post(
        (
            "/api/v1/preferences/"
            "group/profile"
        ),
        json={
            "group_id": "friends",
            "profile_ids": [
                "danya",
                "missing-user",
            ],
        },
    )

    assert (
        response.status_code
        == 404
    )

    detail = response.json()[
        "detail"
    ]

    assert (
        "missing-user"
        in detail[
            "missing_profile_ids"
        ]
    )


def test_duplicate_member_ids_are_rejected(
    monkeypatch,
) -> None:
    client, _ = _client(
        monkeypatch
    )

    response = client.post(
        (
            "/api/v1/preferences/"
            "group/profile"
        ),
        json={
            "group_id": "friends",
            "profile_ids": [
                "danya",
                "danya",
            ],
        },
    )

    assert (
        response.status_code
        == 422
    )


def test_group_profile_does_not_mutate_members(
    monkeypatch,
) -> None:
    client, store = _client(
        monkeypatch
    )

    before = store.get(
        "danya"
    )

    assert before is not None

    response = client.post(
        (
            "/api/v1/preferences/"
            "group/profile"
        ),
        json={
            "group_id": "friends",
            "profile_ids": [
                "danya",
                "misha",
            ],
        },
    )

    assert (
        response.status_code
        == 200
    )

    after = store.get(
        "danya"
    )

    assert after is not None

    assert (
        after.model_dump()
        == before.model_dump()
    )