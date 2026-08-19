from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.preferences as preferences_api

from app.preferences.cold_start_service import (
    ColdStartService,
)
from app.preferences.store import (
    PreferenceStore,
)


def _choices() -> list[dict]:
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


def _client(
    monkeypatch,
) -> tuple[
    TestClient,
    PreferenceStore,
]:
    store = PreferenceStore()

    monkeypatch.setattr(
        preferences_api,
        "get_preference_store",
        lambda: store,
    )

    class TestColdStartService(
        ColdStartService
    ):
        def __init__(
            self,
        ) -> None:
            super().__init__(
                store=store
            )

    monkeypatch.setattr(
        preferences_api,
        "ColdStartService",
        TestColdStartService,
    )

    app = FastAPI()

    app.include_router(
        preferences_api.router
    )

    return (
        TestClient(app),
        store,
    )


def test_questions_endpoint(
    monkeypatch,
) -> None:
    client, _ = _client(
        monkeypatch
    )

    response = client.get(
        (
            "/api/v1/preferences/"
            "cold-start/questions"
        )
    )

    assert (
        response.status_code
        == 200
    )

    data = response.json()

    assert (
        data["total"]
        == 6
    )

    assert (
        data["minimum_choices"]
        == 4
    )

    assert (
        len(
            data["questions"]
        )
        == 6
    )

    assert (
        data[
            "questions"
        ][0][
            "left"
        ][
            "total_price"
        ]
        > 0
    )


def test_questions_can_be_limited(
    monkeypatch,
) -> None:
    client, _ = _client(
        monkeypatch
    )

    response = client.get(
        (
            "/api/v1/preferences/"
            "cold-start/questions"
            "?limit=4"
        )
    )

    assert (
        response.status_code
        == 200
    )

    data = response.json()

    assert (
        data["total"]
        == 4
    )

    assert (
        len(
            data["questions"]
        )
        == 4
    )

    assert (
        data["minimum_choices"]
        == 4
    )


def test_complete_creates_real_profile(
    monkeypatch,
) -> None:
    client, store = _client(
        monkeypatch
    )

    response = client.post(
        (
            "/api/v1/preferences/"
            "cold-start/complete"
        ),
        json={
            "profile_id": (
                "cold-user"
            ),
            "choices": _choices(),
        },
    )

    assert (
        response.status_code
        == 200
    )

    data = response.json()

    assert (
        data[
            "cold_start"
        ][
            "completed"
        ]
        is True
    )

    profile = (
        data["profile"]
    )

    assert (
        profile[
            "cold_start_completed"
        ]
        is True
    )

    assert (
        profile[
            "cold_start_answers"
        ]
        == 4
    )

    assert (
        profile[
            "interactions"
        ]
        == 4
    )

    assert (
        profile[
            "weights"
        ][
            "price"
        ]
        > 0
    )

    saved = store.get(
        "cold-user"
    )

    assert saved is not None

    assert (
        saved
        .cold_start_completed
        is True
    )


def test_created_profile_is_available_via_profile_endpoint(
    monkeypatch,
) -> None:
    client, _ = _client(
        monkeypatch
    )

    complete = client.post(
        (
            "/api/v1/preferences/"
            "cold-start/complete"
        ),
        json={
            "profile_id": (
                "danya"
            ),
            "choices": _choices(),
        },
    )

    assert (
        complete.status_code
        == 200
    )

    response = client.get(
        (
            "/api/v1/preferences/"
            "danya"
        )
    )

    assert (
        response.status_code
        == 200
    )

    data = response.json()

    assert (
        data[
            "profile_id"
        ]
        == "danya"
    )

    assert (
        data[
            "cold_start_completed"
        ]
        is True
    )

    assert (
        data[
            "interactions"
        ]
        == 4
    )


def test_less_than_four_choices_is_rejected(
    monkeypatch,
) -> None:
    client, _ = _client(
        monkeypatch
    )

    response = client.post(
        (
            "/api/v1/preferences/"
            "cold-start/complete"
        ),
        json={
            "profile_id": (
                "partial-user"
            ),
            "choices": (
                _choices()[:3]
            ),
        },
    )

    assert (
        response.status_code
        == 422
    )

    assert (
        "At least 4"
        in response.json()[
            "detail"
        ]
    )


def test_second_completion_requires_replace(
    monkeypatch,
) -> None:
    client, _ = _client(
        monkeypatch
    )

    first = client.post(
        (
            "/api/v1/preferences/"
            "cold-start/complete"
        ),
        json={
            "profile_id": (
                "repeat-user"
            ),
            "choices": _choices(),
        },
    )

    assert (
        first.status_code
        == 200
    )

    second = client.post(
        (
            "/api/v1/preferences/"
            "cold-start/complete"
        ),
        json={
            "profile_id": (
                "repeat-user"
            ),
            "choices": _choices(),
        },
    )

    assert (
        second.status_code
        == 422
    )

    assert (
        "already completed"
        in second.json()[
            "detail"
        ]
    )


def test_replace_does_not_inflate_interactions(
    monkeypatch,
) -> None:
    client, _ = _client(
        monkeypatch
    )

    first = client.post(
        (
            "/api/v1/preferences/"
            "cold-start/complete"
        ),
        json={
            "profile_id": (
                "replace-user"
            ),
            "choices": _choices(),
        },
    )

    assert (
        first.status_code
        == 200
    )

    second = client.post(
        (
            "/api/v1/preferences/"
            "cold-start/complete"
        ),
        json={
            "profile_id": (
                "replace-user"
            ),
            "choices": _choices(),
            "replace": True,
        },
    )

    assert (
        second.status_code
        == 200
    )

    profile = (
        second.json()[
            "profile"
        ]
    )

    assert (
        profile[
            "interactions"
        ]
        == 4
    )

    assert (
        profile[
            "cold_start_answers"
        ]
        == 4
    )


def test_cold_start_signals_are_returned(
    monkeypatch,
) -> None:
    client, _ = _client(
        monkeypatch
    )

    response = client.post(
        (
            "/api/v1/preferences/"
            "cold-start/complete"
        ),
        json={
            "profile_id": (
                "signal-user"
            ),
            "choices": _choices(),
        },
    )

    assert (
        response.status_code
        == 200
    )

    signals = (
        response.json()[
            "learned_signals"
        ]
    )

    assert signals

    assert any(
        (
            "дешёв"
            in signal
        )
        or (
            "выгод"
            in signal
        )
        for signal
        in signals
    )