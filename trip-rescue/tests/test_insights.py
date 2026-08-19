from __future__ import annotations

from datetime import datetime

from app.models.journey import (
    HotelOption,
    JourneyOption,
    TransportSegment,
)
from app.models.trip import (
    TransportMode,
)
from app.rescue.insights import (
    InsightAction,
    InsightSeverity,
    InsightType,
    build_rescue_insights,
)


def _segment(
    *,
    segment_id: str,
    departure: str,
    arrival: str,
) -> TransportSegment:
    return TransportSegment(
        id=segment_id,
        mode=TransportMode.BUS,
        origin="A",
        destination="B",
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
        price=5_000,
        transfers=0,
    )


def _journey(
    *,
    inbound_departure: str,
    hotel: HotelOption | None,
) -> JourneyOption:
    outbound = _segment(
        segment_id="out",
        departure=(
            "2026-08-21T22:45:00+03:00"
        ),
        arrival=(
            "2026-08-22T08:45:00+03:00"
        ),
    )

    inbound = _segment(
        segment_id="back",
        departure=(
            inbound_departure
        ),
        arrival=(
            "2026-08-23T07:00:00+03:00"
        ),
    )

    return JourneyOption(
        id="journey",
        outbound=outbound,
        inbound=inbound,
        hotel=hotel,
        total_price=(
            outbound.price
            + inbound.price
            + (
                hotel.price
                if hotel is not None
                else 0
            )
        ),
    )


def _hotel() -> HotelOption:
    return HotelOption(
        id="hotel",
        name="Мансарда",
        price=3_275,
        check_in="2026-08-22",
        check_out="2026-08-23",
        nights=1,
    )


def test_evening_departure_before_checkout_creates_warning() -> None:
    journey = _journey(
        inbound_departure=(
            "2026-08-22T19:00:00+03:00"
        ),
        hotel=_hotel(),
    )

    insights = (
        build_rescue_insights(
            journey=journey
        )
    )

    assert len(
        insights
    ) == 1

    insight = insights[0]

    assert (
        insight.type
        == InsightType
        .HOTEL_UNUSED_NIGHTS
    )

    assert (
        insight.severity
        == InsightSeverity.WARNING
    )

    assert (
        insight.action
        == InsightAction
        .SEARCH_SHORTER_HOTEL
    )

    assert (
        insight
        .estimated_unused_nights
        == 1
    )

    assert (
        insight.estimated_amount
        == 3_275
    )


def test_departure_on_checkout_date_has_no_warning() -> None:
    journey = _journey(
        inbound_departure=(
            "2026-08-23T05:00:00+03:00"
        ),
        hotel=_hotel(),
    )

    insights = (
        build_rescue_insights(
            journey=journey
        )
    )

    assert insights == []


def test_no_hotel_has_no_warning() -> None:
    journey = _journey(
        inbound_departure=(
            "2026-08-22T19:00:00+03:00"
        ),
        hotel=None,
    )

    insights = (
        build_rescue_insights(
            journey=journey
        )
    )

    assert insights == []


def test_multiple_unused_nights_are_estimated_proportionally() -> None:
    hotel = HotelOption(
        id="hotel",
        name="Test hotel",
        price=9_000,
        check_in="2026-08-21",
        check_out="2026-08-24",
        nights=3,
    )

    journey = _journey(
        inbound_departure=(
            "2026-08-22T18:00:00+03:00"
        ),
        hotel=hotel,
    )

    insights = (
        build_rescue_insights(
            journey=journey
        )
    )

    assert len(
        insights
    ) == 1

    insight = insights[0]

    assert (
        insight
        .estimated_unused_nights
        == 2
    )

    assert (
        insight.estimated_amount
        == 6_000
    )