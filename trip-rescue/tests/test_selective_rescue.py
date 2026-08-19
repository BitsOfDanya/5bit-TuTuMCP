from __future__ import annotations

import asyncio

from datetime import datetime

from app.models.journey import (
    HotelOption,
    JourneyOption,
    TransportSegment,
)
from app.models.rescue import (
    RescueComponent,
    RescuePlanningResult,
    RescuePlanReason,
    RescueSearchPlan,
)
from app.models.trip import (
    TransportMode,
    TripSpec,
)
from app.tutu.rescue_provider import (
    RescueTutuProvider,
)


class ForbiddenBroadProvider:
    """
    Selective tests must never fall back to broad search.
    """

    def __init__(self) -> None:
        self.calls = 0

    async def search_candidates(
        self,
        trip: TripSpec,
    ) -> list[JourneyOption]:
        self.calls += 1

        raise AssertionError(
            "Broad provider must not be called"
        )


class FakeSelectiveProvider:
    def __init__(
        self,
        *,
        inbound: list[
            TransportSegment
        ] | None = None,
        outbound: list[
            TransportSegment
        ] | None = None,
        hotel: HotelOption | None = None,
    ) -> None:
        self.inbound = (
            inbound
            or []
        )

        self.outbound = (
            outbound
            or []
        )

        self.hotel = hotel

        self.inbound_calls = 0
        self.outbound_calls = 0
        self.hotel_calls = 0

    async def search_inbound(
        self,
        *,
        trip: TripSpec,
    ) -> list[TransportSegment]:
        self.inbound_calls += 1
        return self.inbound

    async def search_outbound(
        self,
        *,
        trip: TripSpec,
    ) -> list[TransportSegment]:
        self.outbound_calls += 1
        return self.outbound

    async def search_hotel(
        self,
        *,
        trip: TripSpec,
        current_journey: JourneyOption,
    ) -> HotelOption | None:
        self.hotel_calls += 1
        return self.hotel


def _trip(
    *,
    budget: int = 22_703,
) -> TripSpec:
    return TripSpec(
        origin="Москва",
        destination="Казань",
        outbound_date="2026-08-21",
        return_date="2026-08-23",
        outbound_after="19:00:00",
        return_before="08:00:00",
        travelers=2,
        budget=budget,
        excluded_transport=[],
        preferred_transport=[],
        max_transfers=None,
        hard_constraints={
            "return_before"
        },
    )


def _current() -> JourneyOption:
    outbound = TransportSegment(
        id="old-outbound",
        mode=TransportMode.BUS,
        origin="Москва",
        destination="Казань",
        departure=(
            datetime.fromisoformat(
                "2026-08-21T22:45:00+03:00"
            )
        ),
        arrival=(
            datetime.fromisoformat(
                "2026-08-22T08:45:00+03:00"
            )
        ),
        price=5_000,
        transfers=0,
    )

    inbound = TransportSegment(
        id="old-inbound",
        mode=TransportMode.FLIGHT,
        origin="Казань",
        destination="Москва",
        departure=(
            datetime.fromisoformat(
                "2026-08-23T07:05:00+03:00"
            )
        ),
        arrival=(
            datetime.fromisoformat(
                "2026-08-23T08:40:00+03:00"
            )
        ),
        price=14_428,
        transfers=0,
    )

    hotel = HotelOption(
        id="old-hotel",
        name="Мансарда",
        price=3_275,
        check_in="2026-08-22",
        check_out="2026-08-23",
        nights=1,
    )

    return JourneyOption(
        id="current",
        outbound=outbound,
        hotel=hotel,
        inbound=inbound,
        total_price=22_703,
    )


def _inbound_plan() -> RescuePlanningResult:
    return RescuePlanningResult(
        status="search_required",
        plans=[
            RescueSearchPlan(
                id="replace-inbound",
                reason=(
                    RescuePlanReason
                    .CONSTRAINT_VIOLATION
                ),
                replace_components=[
                    RescueComponent.INBOUND
                ],
                preserve_components=[
                    RescueComponent.OUTBOUND,
                    RescueComponent.HOTEL,
                ],
                mandatory_components=[
                    RescueComponent.INBOUND
                ],
                budget_target_saving=0,
                score=1.0,
                description=(
                    "Replace inbound only"
                ),
            )
        ],
    )


def _return_segment(
    *,
    segment_id: str,
    departure: str,
    arrival: str,
    price: int = 12_000,
) -> TransportSegment:
    return TransportSegment(
        id=segment_id,
        mode=TransportMode.TRAIN,
        origin="Казань",
        destination="Москва",
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


def test_previous_day_departure_can_arrive_before_deadline() -> None:
    segment = _return_segment(
        segment_id="night-train",
        departure=(
            "2026-08-22T20:00:00+03:00"
        ),
        arrival=(
            "2026-08-23T07:30:00+03:00"
        ),
    )

    broad = ForbiddenBroadProvider()

    selective = (
        FakeSelectiveProvider(
            inbound=[
                segment
            ]
        )
    )

    provider = RescueTutuProvider(
        journey_provider=broad,
        selective_provider=selective,
    )

    result = asyncio.run(
        provider.search_replans(
            trip=_trip(),
            current_journey=_current(),
            planning=_inbound_plan(),
        )
    )

    assert (
        result.status
        == "candidates_found"
    )

    assert broad.calls == 0

    assert (
        selective.inbound_calls
        == 1
    )

    candidate = (
        result.candidates[0]
    )

    assert (
        candidate.journey
        .outbound.id
        == "old-outbound"
    )

    assert (
        candidate.journey
        .hotel is not None
    )

    assert (
        candidate.journey
        .hotel.id
        == "old-hotel"
    )

    assert (
        candidate.journey
        .inbound.id
        == "night-train"
    )


def test_arrival_after_hard_deadline_is_rejected() -> None:
    segment = _return_segment(
        segment_id="late-train",
        departure=(
            "2026-08-22T21:00:00+03:00"
        ),
        arrival=(
            "2026-08-23T08:30:00+03:00"
        ),
    )

    provider = RescueTutuProvider(
        journey_provider=(
            ForbiddenBroadProvider()
        ),
        selective_provider=(
            FakeSelectiveProvider(
                inbound=[
                    segment
                ]
            )
        ),
    )

    result = asyncio.run(
        provider.search_replans(
            trip=_trip(),
            current_journey=_current(),
            planning=_inbound_plan(),
        )
    )

    assert (
        result.status
        == "no_candidates"
    )


def test_same_day_early_flight_is_valid() -> None:
    segment = _return_segment(
        segment_id="early-flight",
        departure=(
            "2026-08-23T05:00:00+03:00"
        ),
        arrival=(
            "2026-08-23T06:35:00+03:00"
        ),
        price=11_000,
    )

    provider = RescueTutuProvider(
        journey_provider=(
            ForbiddenBroadProvider()
        ),
        selective_provider=(
            FakeSelectiveProvider(
                inbound=[
                    segment
                ]
            )
        ),
    )

    result = asyncio.run(
        provider.search_replans(
            trip=_trip(),
            current_journey=_current(),
            planning=_inbound_plan(),
        )
    )

    assert (
        result.status
        == "candidates_found"
    )


def test_selective_rescue_does_not_replace_preserved_parts() -> None:
    segment = _return_segment(
        segment_id="replacement",
        departure=(
            "2026-08-23T05:30:00+03:00"
        ),
        arrival=(
            "2026-08-23T07:10:00+03:00"
        ),
        price=10_000,
    )

    current = _current()

    provider = RescueTutuProvider(
        journey_provider=(
            ForbiddenBroadProvider()
        ),
        selective_provider=(
            FakeSelectiveProvider(
                inbound=[
                    segment
                ]
            )
        ),
    )

    result = asyncio.run(
        provider.search_replans(
            trip=_trip(),
            current_journey=current,
            planning=_inbound_plan(),
        )
    )

    journey = (
        result.candidates[0]
        .journey
    )

    assert (
        journey.outbound
        == current.outbound
    )

    assert (
        journey.hotel
        == current.hotel
    )

    assert (
        journey.inbound
        != current.inbound
    )


def test_cheaper_valid_replacement_recalculates_total() -> None:
    segment = _return_segment(
        segment_id="cheap-return",
        departure=(
            "2026-08-23T05:00:00+03:00"
        ),
        arrival=(
            "2026-08-23T07:00:00+03:00"
        ),
        price=9_000,
    )

    provider = RescueTutuProvider(
        journey_provider=(
            ForbiddenBroadProvider()
        ),
        selective_provider=(
            FakeSelectiveProvider(
                inbound=[
                    segment
                ]
            )
        ),
    )

    result = asyncio.run(
        provider.search_replans(
            trip=_trip(),
            current_journey=_current(),
            planning=_inbound_plan(),
        )
    )

    candidate = (
        result.candidates[0]
    )

    assert (
        candidate.new_total_price
        == 17_275
    )

    assert (
        candidate.price_delta
        == -5_428
    )