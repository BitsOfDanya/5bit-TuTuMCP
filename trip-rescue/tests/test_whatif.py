from __future__ import annotations

from datetime import datetime

import pytest

from app.models.journey import (
    HotelOption,
    JourneyOption,
    TransportSegment,
)
from app.models.rescue import (
    RescueComponent,
    TripField,
)
from app.models.trip import (
    ConstraintField,
    TransportMode,
    TripSpec,
)
from app.tutu.whatif_provider import (
    WhatIfTutuProvider,
)
from app.whatif.engine import (
    WhatIfEngine,
)
from app.whatif.models import (
    WhatIfStatus,
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
        id="hotel-current",
        name="Test Hotel",
        price=3_000,
        rating=8.5,
        check_in="2026-08-22",
        check_out="2026-08-23",
        nights=1,
    )


def _current_journey() -> JourneyOption:
    outbound = _segment(
        segment_id="out-current",
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
    )

    inbound = _segment(
        segment_id="in-current",
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
    )

    hotel = _hotel()

    return JourneyOption(
        id="current",
        outbound=outbound,
        inbound=inbound,
        hotel=hotel,
        total_price=15_000,
    )


def _trip(
    *,
    return_before: str = "08:00:00",
) -> TripSpec:
    return TripSpec(
        origin="Москва",
        destination="Казань",
        outbound_date="2026-08-21",
        return_date="2026-08-23",
        outbound_after="19:00:00",
        return_before=return_before,
        travelers=1,
        budget=30_000,
        excluded_transport=[],
        preferred_transport=[],
        max_transfers=None,
        hard_constraints=[
            ConstraintField.RETURN_BEFORE
        ],
    )


def _cheaper_later_journey() -> JourneyOption:
    current = (
        _current_journey()
    )

    inbound = _segment(
        segment_id="in-cheaper",
        mode=TransportMode.TRAIN,
        origin="Казань",
        destination="Москва",
        departure=(
            "2026-08-22"
            "T21:00:00+03:00"
        ),
        arrival=(
            "2026-08-23"
            "T09:30:00+03:00"
        ),
        price=4_000,
    )

    return JourneyOption(
        id="cheaper-later",
        outbound=(
            current.outbound
        ),
        inbound=inbound,
        hotel=current.hotel,
        total_price=12_000,
    )


class FakeProvider:
    def __init__(
        self,
        journeys: list[
            JourneyOption
        ],
    ) -> None:
        self.journeys = journeys

        self.calls = 0

    async def search_alternatives(
        self,
        *,
        trip: TripSpec,
        current_journey: JourneyOption,
        changed_fields: list[
            TripField
        ],
        limit: int = 30,
    ) -> list[
        JourneyOption
    ]:
        self.calls += 1

        return self.journeys[
            :limit
        ]


@pytest.mark.asyncio
async def test_relaxed_deadline_explores_even_if_baseline_valid() -> None:
    current_trip = _trip(
        return_before="08:00:00"
    )

    hypothetical = _trip(
        return_before="10:00:00"
    )

    journey = (
        _current_journey()
    )

    provider = FakeProvider(
        [
            _cheaper_later_journey()
        ]
    )

    engine = WhatIfEngine(
        provider=provider,
    )

    result = await (
        engine.simulate_from_spec(
            current_trip=current_trip,
            hypothetical_trip=(
                hypothetical
            ),
            current_journey=journey,
        )
    )

    assert (
        result.status
        == WhatIfStatus
        .ALTERNATIVES_FOUND
    )

    assert (
        result.baseline_valid
        is True
    )

    assert (
        provider.calls
        == 1
    )

    assert (
        len(result.candidates)
        == 1
    )

    candidate = (
        result.candidates[0]
    )

    assert (
        candidate.journey.total_price
        == 12_000
    )

    assert (
        candidate.impact.price_delta
        == -3_000
    )

    assert (
        candidate.impact.savings
        == 3_000
    )

    assert (
        candidate
        .impact
        .inbound_arrival_delta_minutes
        == 150
    )

    assert (
        candidate
        .impact
        .components_changed
        == [
            RescueComponent.INBOUND
        ]
    )

    # Simulation must not mutate accepted state.
    assert (
        current_trip.return_before
        .isoformat()
        == "08:00:00"
    )

    assert (
        journey.inbound.arrival.hour
        == 7
    )


@pytest.mark.asyncio
async def test_same_trip_does_not_search() -> None:
    trip = _trip()

    provider = FakeProvider(
        [
            _cheaper_later_journey()
        ]
    )

    engine = WhatIfEngine(
        provider=provider,
    )

    result = await (
        engine.simulate_from_spec(
            current_trip=trip,
            hypothetical_trip=(
                trip.model_copy(
                    deep=True
                )
            ),
            current_journey=(
                _current_journey()
            ),
        )
    )

    assert (
        result.status
        == WhatIfStatus
        .NO_DIFFERENCE
    )

    assert (
        provider.calls
        == 0
    )

    assert (
        result.candidates
        == []
    )


@pytest.mark.asyncio
async def test_no_alternatives_is_valid_result() -> None:
    current_trip = _trip(
        return_before="08:00:00"
    )

    hypothetical = _trip(
        return_before="10:00:00"
    )

    provider = FakeProvider(
        []
    )

    engine = WhatIfEngine(
        provider=provider,
    )

    result = await (
        engine.simulate_from_spec(
            current_trip=current_trip,
            hypothetical_trip=(
                hypothetical
            ),
            current_journey=(
                _current_journey()
            ),
        )
    )

    assert (
        result.status
        == WhatIfStatus
        .NO_ALTERNATIVES
    )

    assert (
        result.baseline_valid
        is True
    )


@pytest.mark.asyncio
async def test_minimal_change_ranks_before_full_rebuild() -> None:
    current = (
        _current_journey()
    )

    inbound_only = (
        _cheaper_later_journey()
    )

    full_outbound = _segment(
        segment_id="out-full",
        mode=TransportMode.TRAIN,
        origin="Москва",
        destination="Казань",
        departure=(
            "2026-08-21"
            "T21:00:00+03:00"
        ),
        arrival=(
            "2026-08-22"
            "T06:00:00+03:00"
        ),
        price=1_000,
    )

    full_inbound = _segment(
        segment_id="in-full",
        mode=TransportMode.TRAIN,
        origin="Казань",
        destination="Москва",
        departure=(
            "2026-08-22"
            "T20:00:00+03:00"
        ),
        arrival=(
            "2026-08-23"
            "T09:00:00+03:00"
        ),
        price=1_000,
    )

    full = JourneyOption(
        id="full-rebuild",
        outbound=full_outbound,
        inbound=full_inbound,
        hotel=current.hotel,
        total_price=5_000,
    )

    provider = FakeProvider(
        [
            full,
            inbound_only,
        ]
    )

    engine = WhatIfEngine(
        provider=provider,
    )

    result = await (
        engine.simulate_from_spec(
            current_trip=_trip(
                return_before="08:00:00"
            ),
            hypothetical_trip=_trip(
                return_before="10:00:00"
            ),
            current_journey=current,
        )
    )

    assert (
        result.candidates[0].id
        == "cheaper-later"
    )

    assert (
        result.candidates[0]
        .impact
        .disruption_count
        == 1
    )

    assert (
        result.candidates[1]
        .impact
        .disruption_count
        == 2
    )


class FakeSelective:
    def __init__(
        self,
    ) -> None:
        self.outbound_calls = 0
        self.inbound_calls = 0
        self.hotel_calls = 0

    async def search_outbound(
        self,
        *,
        trip: TripSpec,
    ) -> list[
        TransportSegment
    ]:
        self.outbound_calls += 1
        return []

    async def search_inbound(
        self,
        *,
        trip: TripSpec,
    ) -> list[
        TransportSegment
    ]:
        self.inbound_calls += 1

        return [
            _cheaper_later_journey()
            .inbound
        ]

    async def search_hotel(
        self,
        *,
        trip: TripSpec,
        current_journey: JourneyOption,
    ) -> HotelOption | None:
        self.hotel_calls += 1
        return None


class FakeBroad:
    def __init__(
        self,
    ) -> None:
        self.calls = 0

    async def search_candidates(
        self,
        trip: TripSpec,
    ) -> list[
        JourneyOption
    ]:
        self.calls += 1
        return []


@pytest.mark.asyncio
async def test_return_deadline_uses_only_selective_inbound_search() -> None:
    selective = FakeSelective()
    broad = FakeBroad()

    provider = WhatIfTutuProvider(
        journey_provider=broad,
        selective_provider=selective,
    )

    current = (
        _current_journey()
    )

    journeys = (
        await provider
        .search_alternatives(
            trip=_trip(
                return_before="10:00:00"
            ),
            current_journey=current,
            changed_fields=[
                TripField.RETURN_BEFORE,
                TripField.HARD_CONSTRAINTS,
            ],
        )
    )

    assert (
        selective.inbound_calls
        == 1
    )

    assert (
        selective.outbound_calls
        == 0
    )

    assert (
        selective.hotel_calls
        == 0
    )

    assert (
        broad.calls
        == 0
    )

    assert (
        len(journeys)
        == 1
    )

    result = journeys[0]

    assert (
        result.outbound
        == current.outbound
    )

    assert (
        result.hotel
        == current.hotel
    )

    assert (
        result.inbound.id
        == "in-cheaper"
    )