from __future__ import annotations

from datetime import datetime

from app.models.journey import (
    JourneyOption,
    TransportSegment,
)
from app.models.rescue import (
    RescueCandidate,
    RescueComponent,
)
from app.models.trip import (
    TransportMode,
)
from app.preferences.learner import (
    PreferenceLearner,
)
from app.preferences.models import (
    PreferenceAction,
)
from app.preferences.scorer import (
    rerank_rescue_candidates,
)
from app.preferences.store import (
    PreferenceStore,
)


def _segment(
    *,
    segment_id: str,
    mode: TransportMode,
    departure: str,
    arrival: str,
    price: int,
    transfers: int = 0,
) -> TransportSegment:
    return TransportSegment(
        id=segment_id,
        mode=mode,
        origin="Москва",
        destination="Казань",
        departure=(
            datetime.fromisoformat(
                departure
            )
        ),
        arrival=(
            datetime.fromisoformat(
                arrival
            )
        ),
        price=price,
        transfers=transfers,
    )


def _journey(
    *,
    journey_id: str,
    mode: TransportMode,
    total_price: int,
    duration_hours: int,
    transfers: int = 0,
) -> JourneyOption:

    half_price = (
        total_price // 2
    )

    outbound = _segment(
        segment_id=(
            f"{journey_id}-out"
        ),
        mode=mode,
        departure=(
            "2026-08-21T10:00:00+03:00"
        ),
        arrival=(
            (
                "2026-08-21T"
                f"{10 + duration_hours:02d}"
                ":00:00+03:00"
            )
        ),
        price=half_price,
        transfers=transfers,
    )

    inbound = _segment(
        segment_id=(
            f"{journey_id}-back"
        ),
        mode=mode,
        departure=(
            "2026-08-23T10:00:00+03:00"
        ),
        arrival=(
            (
                "2026-08-23T"
                f"{10 + duration_hours:02d}"
                ":00:00+03:00"
            )
        ),
        price=(
            total_price
            - half_price
        ),
        transfers=transfers,
    )

    return JourneyOption(
        id=journey_id,
        outbound=outbound,
        inbound=inbound,
        hotel=None,
        total_price=total_price,
    )


def _candidate(
    *,
    journey: JourneyOption,
    base_score: float,
) -> RescueCandidate:

    return RescueCandidate(
        id=(
            f"candidate:{journey.id}"
        ),
        search_plan_id=(
            "test-plan"
        ),
        replaced_components=[
            RescueComponent.INBOUND
        ],
        preserved_components=[
            RescueComponent.OUTBOUND
        ],
        journey=journey,
        previous_total_price=20_000,
        new_total_price=(
            journey.total_price
        ),
        price_delta=(
            journey.total_price
            - 20_000
        ),
        score=base_score,
        exact=True,
        relaxations=[],
        suggested_trip=None,
    )


def test_like_builds_positive_transport_affinity() -> None:
    store = PreferenceStore()

    learner = PreferenceLearner(
        store=store
    )

    bus = _journey(
        journey_id="bus",
        mode=TransportMode.BUS,
        total_price=10_000,
        duration_hours=5,
    )

    result = learner.learn(
        profile_id="user-1",
        action=PreferenceAction.LIKE,
        candidate=bus,
    )

    assert (
        result.profile.interactions
        == 1
    )

    assert (
        result.profile
        .transport_affinity[
            "bus"
        ]
        > 0
    )


def test_dislike_builds_negative_transport_affinity() -> None:
    store = PreferenceStore()

    learner = PreferenceLearner(
        store=store
    )

    bus = _journey(
        journey_id="bus",
        mode=TransportMode.BUS,
        total_price=10_000,
        duration_hours=5,
    )

    result = learner.learn(
        profile_id="user-1",
        action=(
            PreferenceAction.DISLIKE
        ),
        candidate=bus,
    )

    assert (
        result.profile
        .transport_affinity[
            "bus"
        ]
        < 0
    )


def test_choose_cheaper_option_learns_price_importance() -> None:
    store = PreferenceStore()

    learner = PreferenceLearner(
        store=store
    )

    cheap = _journey(
        journey_id="cheap",
        mode=TransportMode.BUS,
        total_price=10_000,
        duration_hours=5,
    )

    expensive = _journey(
        journey_id="expensive",
        mode=TransportMode.FLIGHT,
        total_price=30_000,
        duration_hours=2,
    )

    result = learner.learn(
        profile_id="user-1",
        action=PreferenceAction.CHOOSE,
        candidate=cheap,
        shown_candidates=[
            cheap,
            expensive,
        ],
    )

    assert (
        result.profile
        .weights
        .price
        > 0
    )


def test_choose_flight_learns_flight_affinity() -> None:
    store = PreferenceStore()

    learner = PreferenceLearner(
        store=store
    )

    flight = _journey(
        journey_id="flight",
        mode=TransportMode.FLIGHT,
        total_price=20_000,
        duration_hours=2,
    )

    bus = _journey(
        journey_id="bus",
        mode=TransportMode.BUS,
        total_price=10_000,
        duration_hours=10,
    )

    result = learner.learn(
        profile_id="user-1",
        action=PreferenceAction.CHOOSE,
        candidate=flight,
        shown_candidates=[
            flight,
            bus,
        ],
    )

    profile = (
        result.profile
    )

    assert (
        profile.transport_affinity[
            "flight"
        ]
        > 0
    )

    assert (
        profile.transport_affinity.get(
            "bus",
            0,
        )
        < profile.transport_affinity[
            "flight"
        ]
    )


def test_profiles_are_isolated() -> None:
    store = PreferenceStore()

    learner = PreferenceLearner(
        store=store
    )

    bus = _journey(
        journey_id="bus",
        mode=TransportMode.BUS,
        total_price=10_000,
        duration_hours=5,
    )

    learner.learn(
        profile_id="alice",
        action=PreferenceAction.LIKE,
        candidate=bus,
    )

    bob = (
        store.get_or_create(
            "bob"
        )
    )

    assert (
        bob.interactions
        == 0
    )

    assert (
        bob.transport_affinity
        == {}
    )


def test_reranker_uses_learned_transport_preference() -> None:
    store = PreferenceStore()

    learner = PreferenceLearner(
        store=store
    )

    flight = _journey(
        journey_id="flight",
        mode=TransportMode.FLIGHT,
        total_price=15_000,
        duration_hours=2,
    )

    bus = _journey(
        journey_id="bus",
        mode=TransportMode.BUS,
        total_price=14_000,
        duration_hours=5,
    )

    # Teach the model multiple times to create
    # a strong preference for flight.
    for _ in range(5):
        learner.learn(
            profile_id="user-1",
            action=PreferenceAction.LIKE,
            candidate=flight,
        )

    profile = (
        store.get(
            "user-1"
        )
    )

    assert (
        profile is not None
    )

    candidates = [
        _candidate(
            journey=bus,
            base_score=1.00,
        ),
        _candidate(
            journey=flight,
            base_score=1.03,
        ),
    ]

    ranked = (
        rerank_rescue_candidates(
            candidates=candidates,
            profile=profile,
        )
    )

    assert (
        ranked[0]
        .candidate
        .journey
        .id
        == "flight"
    )

    assert (
        ranked[0].rank_before
        == 2
    )

    assert (
        ranked[0].rank_after
        == 1
    )


def test_store_can_persist_profiles(
    tmp_path,
) -> None:
    path = (
        tmp_path
        / "preferences.json"
    )

    store = PreferenceStore(
        persist_path=str(
            path
        )
    )

    learner = PreferenceLearner(
        store=store
    )

    journey = _journey(
        journey_id="flight",
        mode=TransportMode.FLIGHT,
        total_price=15_000,
        duration_hours=2,
    )

    learner.learn(
        profile_id="persisted-user",
        action=PreferenceAction.LIKE,
        candidate=journey,
    )

    restored = (
        PreferenceStore(
            persist_path=str(
                path
            )
        )
    )

    profile = restored.get(
        "persisted-user"
    )

    assert profile is not None

    assert (
        profile.interactions
        == 1
    )

    assert (
        profile
        .transport_affinity[
            "flight"
        ]
        > 0
    )