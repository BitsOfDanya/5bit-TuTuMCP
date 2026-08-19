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


def _hotel() -> HotelOption:
    return HotelOption(
        id="hotel",
        name="Test Hotel",
        price=3_000,
        check_in="2026-08-22",
        check_out="2026-08-23",
        nights=1,
    )


def _baseline() -> JourneyOption:
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
            segment_id="in-old",
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
        hotel=_hotel(),
        total_price=22_000,
    )


def _candidate() -> JourneyOption:
    baseline = _baseline()

    return JourneyOption(
        id="candidate",
        outbound=baseline.outbound,
        inbound=_segment(
            segment_id="in-new",
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
        hotel=baseline.hotel,
        total_price=15_000,
    )


def _trip() -> TripSpec:
    return TripSpec(
        origin="Москва",
        destination="Казань",
        outbound_date="2026-08-21",
        return_date="2026-08-23",
        return_before="08:00:00",
        travelers=1,
        budget=20_000,
        excluded_transport=[],
        preferred_transport=[],
        max_transfers=None,
        hard_constraints=[
            ConstraintField
            .RETURN_BEFORE,
            ConstraintField
            .BUDGET,
        ],
    )


def test_explanation_preserves_components() -> None:
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
        )
    )

    assert (
        explanation.headline
        == "Меняем только дорогу обратно"
    )

    assert (
        explanation
        .preserved_components
        == [
            RescueComponent.OUTBOUND,
            RescueComponent.HOTEL,
        ]
    )


def test_explanation_describes_savings() -> None:
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
        )
    )

    price_reasons = [
        item.text
        for item
        in explanation.reasons
        if (
            item.type
            == ExplanationType.PRICE
        )
    ]

    assert (
        "Поездка становится дешевле "
        "на 7 000 ₽."
        in price_reasons
    )


def test_explanation_checks_hard_deadline() -> None:
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
        )
    )

    constraint_reasons = [
        item.text
        for item
        in explanation.reasons
        if (
            item.type
            == ExplanationType
            .CONSTRAINT
        )
    ]

    assert any(
        "возвращения выполнено"
        in text
        for text
        in constraint_reasons
    )


def test_preference_reasons_are_included() -> None:
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
                    "более дешёвые варианты."
                )
            ],
        )
    )

    assert any(
        item.type
        == ExplanationType.PREFERENCE
        for item
        in explanation.reasons
    )


def test_insights_become_tradeoffs() -> None:
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
            insight_reasons=[
                (
                    "Одна ночь отеля "
                    "может не понадобиться."
                )
            ],
        )
    )

    assert any(
        item.type
        == ExplanationType.INSIGHT
        for item
        in explanation.tradeoffs
    )