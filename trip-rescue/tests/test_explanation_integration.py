from __future__ import annotations

from datetime import datetime

from app.explanations.engine import (
    build_decision_explanation,
)
from app.explanations.models import (
    ExplanationType,
)
from app.models.journey import (
    HotelOption,
    JourneyOption,
    TransportSegment,
)
from app.models.rescue import (
    RescueComponent,
)
from app.models.trip import (
    ConstraintField,
    TransportMode,
    TripSpec,
)
from app.whatif.analyzer import (
    build_whatif_impact,
)
from app.whatif.models import (
    WhatIfCandidate,
)
from app.whatif.presenter import (
    to_public_whatif_candidate,
)


def _segment(
    *,
    segment_id: str,
    mode: TransportMode,
    origin: str,
    destination: str,
    departure: str,
    arrival: str,
    price: int,
) -> TransportSegment:
    return TransportSegment(
        id=segment_id,
        mode=mode,
        origin=origin,
        destination=destination,
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
        transfers=0,
    )


def _baseline() -> JourneyOption:
    hotel = HotelOption(
        id="hotel",
        name="Test Hotel",
        price=3_000,
        check_in="2026-08-22",
        check_out="2026-08-23",
        nights=1,
    )

    return JourneyOption(
        id="baseline",
        outbound=_segment(
            segment_id="out",
            mode=TransportMode.BUS,
            origin="Москва",
            destination="Казань",
            departure=(
                "2026-08-21"
                "T22:00:00+03:00"
            ),
            arrival=(
                "2026-08-22"
                "T08:00:00+03:00"
            ),
            price=5_000,
        ),
        inbound=_segment(
            segment_id="old-in",
            mode=TransportMode.FLIGHT,
            origin="Казань",
            destination="Москва",
            departure=(
                "2026-08-23"
                "T07:00:00+03:00"
            ),
            arrival=(
                "2026-08-23"
                "T08:40:00+03:00"
            ),
            price=14_000,
        ),
        hotel=hotel,
        total_price=22_000,
    )


def _candidate() -> JourneyOption:
    baseline = _baseline()

    return JourneyOption(
        id="candidate",
        outbound=baseline.outbound,
        hotel=baseline.hotel,
        inbound=_segment(
            segment_id="new-in",
            mode=TransportMode.BUS,
            origin="Казань",
            destination="Москва",
            departure=(
                "2026-08-22"
                "T19:00:00+03:00"
            ),
            arrival=(
                "2026-08-23"
                "T07:00:00+03:00"
            ),
            price=7_000,
        ),
        total_price=15_000,
    )


def _trip() -> TripSpec:
    return TripSpec(
        origin="Москва",
        destination="Казань",
        outbound_date="2026-08-21",
        return_date="2026-08-23",
        outbound_after="19:00:00",
        return_before="08:00:00",
        travelers=1,
        budget=20_000,
        excluded_transport=[],
        preferred_transport=[],
        max_transfers=None,
        hard_constraints=[
            ConstraintField
            .RETURN_BEFORE,
            ConstraintField.BUDGET,
        ],
    )


def test_combined_explanation_contains_all_layers() -> None:
    explanation = (
        build_decision_explanation(
            trip=_trip(),
            baseline=_baseline(),
            candidate=_candidate(),
            preserved_components=[
                RescueComponent.OUTBOUND,
                RescueComponent.HOTEL,
            ],
            changed_components=[
                RescueComponent.INBOUND
            ],
            preference_reasons=[
                (
                    "Ты чаще выбираешь "
                    "более выгодные варианты."
                )
            ],
            insight_reasons=[
                (
                    "Часть брони отеля "
                    "может не понадобиться."
                )
            ],
            tradeoff_reasons=[
                (
                    "Для этого сценария "
                    "потребуется изменить "
                    "одно мягкое условие."
                )
            ],
        )
    )

    types = {
        item.type
        for item
        in (
            explanation.reasons
            + explanation.tradeoffs
        )
    }

    assert (
        ExplanationType.PRESERVATION
        in types
    )

    assert (
        ExplanationType.CONSTRAINT
        in types
    )

    assert (
        ExplanationType.PRICE
        in types
    )

    assert (
        ExplanationType.SCHEDULE
        in types
    )

    assert (
        ExplanationType.PREFERENCE
        in types
    )

    assert (
        ExplanationType.INSIGHT
        in types
    )

    assert (
        ExplanationType.TRADEOFF
        in types
    )


def test_whatif_candidate_gets_explanation() -> None:
    baseline = _baseline()
    candidate = _candidate()

    impact = build_whatif_impact(
        current=baseline,
        candidate=candidate,
    )

    whatif = WhatIfCandidate(
        id="what-if-1",
        rank=1,
        journey=candidate,
        impact=impact,
    )

    public = (
        to_public_whatif_candidate(
            candidate=whatif,
            trip=_trip(),
            baseline=baseline,
        )
    )

    assert (
        public.explanation.headline
        == "Меняем только дорогу обратно"
    )

    assert (
        public.explanation.summary
    )

    assert any(
        item.type
        == ExplanationType.PRICE
        for item
        in public.explanation.reasons
    )

    assert any(
        item.type
        == ExplanationType.CONSTRAINT
        for item
        in public.explanation.reasons
    )