from __future__ import annotations

from typing import Protocol

from app.models.journey import (
    HotelOption,
    JourneyOption,
    TransportSegment,
)
from app.models.rescue import (
    TripField,
)
from app.models.trip import (
    TripSpec,
)
from app.rescue.feasibility import (
    journey_satisfies_trip,
)
from app.whatif.analyzer import (
    journey_is_materially_same,
)


class BroadWhatIfProvider(
    Protocol
):
    async def search_candidates(
        self,
        trip: TripSpec,
    ) -> list[
        JourneyOption
    ]:
        ...


class SelectiveWhatIfProvider(
    Protocol
):
    async def search_outbound(
        self,
        *,
        trip: TripSpec,
    ) -> list[
        TransportSegment
    ]:
        ...

    async def search_inbound(
        self,
        *,
        trip: TripSpec,
    ) -> list[
        TransportSegment
    ]:
        ...

    async def search_hotel(
        self,
        *,
        trip: TripSpec,
        current_journey: JourneyOption,
    ) -> HotelOption | None:
        ...


class WhatIfTutuProvider:
    """
    Search provider dedicated to hypothetical exploration.

    Main difference from RescueTutuProvider:

    Rescue:
        searches because current journey became invalid.

    What-if:
        searches because user wants to know what ELSE
        becomes possible under hypothetical conditions.

    Therefore baseline validity does not stop the search.
    """

    def __init__(
        self,
        *,
        journey_provider: (
            BroadWhatIfProvider
            | None
        ) = None,
        selective_provider: (
            SelectiveWhatIfProvider
            | None
        ) = None,
    ) -> None:
        production_defaults = (
            journey_provider is None
        )

        if journey_provider is None:
            from app.tutu.provider import (
                TutuMCPJourneyProvider,
            )

            journey_provider = (
                TutuMCPJourneyProvider()
            )

        self.journey_provider = (
            journey_provider
        )

        if (
            selective_provider is None
            and production_defaults
        ):
            from app.tutu.selective_provider import (
                TutuSelectiveProvider,
            )

            full_provider = (
                self.journey_provider
            )

            selective_provider = (
                TutuSelectiveProvider(
                    client=getattr(
                        full_provider,
                        "client",
                        None,
                    ),
                    normalizer=getattr(
                        full_provider,
                        "normalizer",
                        None,
                    ),
                    hotel_provider=getattr(
                        full_provider,
                        "hotel_provider",
                        None,
                    ),
                )
            )

        self.selective_provider = (
            selective_provider
        )

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
        strategy = (
            _build_search_strategy(
                changed_fields
            )
        )

        journeys: list[
            JourneyOption
        ] = []

        if (
            strategy.search_outbound
            and self.selective_provider
            is not None
        ):
            segments = (
                await self
                .selective_provider
                .search_outbound(
                    trip=trip
                )
            )

            journeys.extend(
                _assemble_journey(
                    outbound=segment,
                    hotel=(
                        current_journey.hotel
                    ),
                    inbound=(
                        current_journey.inbound
                    ),
                )
                for segment
                in segments
            )

        if (
            strategy.search_inbound
            and self.selective_provider
            is not None
        ):
            segments = (
                await self
                .selective_provider
                .search_inbound(
                    trip=trip
                )
            )

            journeys.extend(
                _assemble_journey(
                    outbound=(
                        current_journey.outbound
                    ),
                    hotel=(
                        current_journey.hotel
                    ),
                    inbound=segment,
                )
                for segment
                in segments
            )

        if (
            strategy.search_hotel
            and current_journey.hotel
            is not None
            and self.selective_provider
            is not None
        ):
            hotel = (
                await self
                .selective_provider
                .search_hotel(
                    trip=trip,
                    current_journey=(
                        current_journey
                    ),
                )
            )

            if hotel is not None:
                journeys.append(
                    _assemble_journey(
                        outbound=(
                            current_journey
                            .outbound
                        ),
                        hotel=hotel,
                        inbound=(
                            current_journey
                            .inbound
                        ),
                    )
                )

        if strategy.search_broad:
            broad = (
                await self
                .journey_provider
                .search_candidates(
                    trip
                )
            )

            for journey in broad:
                if not _compatible_trip_shape(
                    current=(
                        current_journey
                    ),
                    candidate=journey,
                ):
                    continue

                journeys.append(
                    journey
                )

        result: list[
            JourneyOption
        ] = []

        seen: set[
            tuple
        ] = set()

        for journey in journeys:
            if journey_is_materially_same(
                current_journey,
                journey,
            ):
                continue

            if not journey_satisfies_trip(
                trip=trip,
                journey=journey,
            ):
                continue

            signature = (
                _journey_signature(
                    journey
                )
            )

            if signature in seen:
                continue

            seen.add(
                signature
            )

            result.append(
                journey
            )

        result.sort(
            key=lambda journey: (
                journey.total_price,
                journey.inbound.arrival,
                journey.outbound.departure,
                journey.id,
            )
        )

        return result[
            :max(
                0,
                limit,
            )
        ]


class _SearchStrategy:
    def __init__(
        self,
        *,
        search_outbound: bool = False,
        search_inbound: bool = False,
        search_hotel: bool = False,
        search_broad: bool = False,
    ) -> None:
        self.search_outbound = (
            search_outbound
        )

        self.search_inbound = (
            search_inbound
        )

        self.search_hotel = (
            search_hotel
        )

        self.search_broad = (
            search_broad
        )


def _build_search_strategy(
    changed_fields: list[
        TripField
    ],
) -> _SearchStrategy:
    fields = set(
        changed_fields
    )

    # Hardness itself changes validation semantics,
    # but does not identify another physical component
    # to search.
    fields.discard(
        TripField.HARD_CONSTRAINTS
    )

    if not fields:
        return _SearchStrategy()

    broad_fields = {
        TripField.ORIGIN,
        TripField.DESTINATION,
        TripField.OUTBOUND_DATE,
        TripField.RETURN_DATE,
        TripField.TRAVELERS,
    }

    if (
        fields
        & broad_fields
    ):
        return _SearchStrategy(
            search_broad=True
        )

    if (
        TripField.BUDGET
        in fields
    ):
        return _SearchStrategy(
            search_outbound=True,
            search_inbound=True,
            search_hotel=True,
            search_broad=True,
        )

    search_outbound = (
        TripField.OUTBOUND_AFTER
        in fields
    )

    search_inbound = (
        TripField.RETURN_BEFORE
        in fields
    )

    transport_fields = {
        TripField.EXCLUDED_TRANSPORT,
        TripField.PREFERRED_TRANSPORT,
        TripField.MAX_TRANSFERS,
    }

    if (
        fields
        & transport_fields
    ):
        search_outbound = True
        search_inbound = True

    search_broad = (
        (
            search_outbound
            and search_inbound
        )
        or bool(
            fields
            & transport_fields
        )
    )

    return _SearchStrategy(
        search_outbound=(
            search_outbound
        ),
        search_inbound=(
            search_inbound
        ),
        search_broad=(
            search_broad
        ),
    )


def _assemble_journey(
    *,
    outbound: TransportSegment,
    hotel: HotelOption | None,
    inbound: TransportSegment,
) -> JourneyOption:
    total_price = (
        outbound.price
        + inbound.price
        + (
            hotel.price
            if hotel is not None
            else 0
        )
    )

    hotel_id = (
        hotel.id
        if hotel is not None
        else "no-hotel"
    )

    return JourneyOption(
        id=(
            "whatif:"
            f"{outbound.id}:"
            f"{hotel_id}:"
            f"{inbound.id}"
        ),
        outbound=outbound,
        hotel=hotel,
        inbound=inbound,
        total_price=total_price,
    )


def _compatible_trip_shape(
    *,
    current: JourneyOption,
    candidate: JourneyOption,
) -> bool:
    """
    What-if must not silently remove or add lodging.

    TripSpec currently does not encode a dedicated
    "hotel required" flag, therefore the accepted journey
    is the source of truth for whether lodging is part
    of this trip.
    """

    return (
        (current.hotel is None)
        == (candidate.hotel is None)
    )


def _journey_signature(
    journey: JourneyOption,
) -> tuple:
    hotel = (
        journey.hotel
    )

    return (
        journey.outbound.mode.value,
        journey.outbound.origin,
        journey.outbound.destination,
        journey.outbound.departure,
        journey.outbound.arrival,
        journey.outbound.price,

        (
            hotel.name
            if hotel is not None
            else None
        ),

        (
            hotel.check_in
            if hotel is not None
            else None
        ),

        (
            hotel.check_out
            if hotel is not None
            else None
        ),

        (
            hotel.price
            if hotel is not None
            else None
        ),

        journey.inbound.mode.value,
        journey.inbound.origin,
        journey.inbound.destination,
        journey.inbound.departure,
        journey.inbound.arrival,
        journey.inbound.price,
    )