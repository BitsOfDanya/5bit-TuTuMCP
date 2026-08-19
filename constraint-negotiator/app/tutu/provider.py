from __future__ import annotations

import asyncio
from datetime import date

from app.models.journey import (
    HotelOption,
    JourneyOption,
    TransportSegment,
)
from app.models.trip import TripSpec
from app.tutu.client import TutuMCPClient
from app.tutu.hotel_provider import (
    TutuHotelProvider,
)
from app.tutu.normalizer import (
    TutuSearchNormalizer,
)


StayKey = tuple[date, date]


class TutuMCPJourneyProvider:
    """
    Broad full-trip provider for Constraint Negotiator.

    Flow:

        transport outbound
            +
        transport inbound
            ↓
        determine stay dates
            ↓
        search hotel once per unique stay window
            ↓
        attach cheapest fetched hotel candidate
            ↓
        complete JourneyOption
            ↓
        Constraint Negotiator

    User constraints are intentionally NOT pushed
    into MCP search, because the solver needs to see
    violating candidates to propose relaxations.
    """

    def __init__(
        self,
        client: TutuMCPClient | None = None,
        normalizer: TutuSearchNormalizer | None = None,
        hotel_provider: TutuHotelProvider | None = None,
    ) -> None:

        self.client = (
            client
            or TutuMCPClient()
        )

        self.normalizer = (
            normalizer
            or TutuSearchNormalizer()
        )

        self.hotel_provider = (
            hotel_provider
            or TutuHotelProvider(
                client=self.client
            )
        )

    async def search_candidates(
        self,
        trip: TripSpec,
    ) -> list[JourneyOption]:

        outbound_task = (
            self._search_direction(
                origin=trip.origin,
                destination=trip.destination,
                departure_date=(
                    trip.outbound_date
                    .isoformat()
                ),
                travelers=trip.travelers,
            )
        )

        inbound_task = (
            self._search_direction(
                origin=trip.destination,
                destination=trip.origin,
                departure_date=(
                    trip.return_date
                    .isoformat()
                ),
                travelers=trip.travelers,
            )
        )

        outbound, inbound = (
            await asyncio.gather(
                outbound_task,
                inbound_task,
            )
        )

        if not outbound or not inbound:
            return []

        transport_pairs = (
            self._build_transport_pairs(
                outbound=outbound,
                inbound=inbound,
            )
        )

        if not transport_pairs:
            return []

        stay_keys = {
            stay_key
            for _, _, stay_key
            in transport_pairs
            if stay_key is not None
        }

        hotels_by_stay = (
            await self._load_hotels(
                city=trip.destination,
                stay_keys=stay_keys,
                travelers=trip.travelers,
            )
        )

        journeys: list[
            JourneyOption
        ] = []

        for (
            out,
            back,
            stay_key,
        ) in transport_pairs:

            hotel: HotelOption | None = None

            if stay_key is not None:
                hotel = hotels_by_stay.get(
                    stay_key
                )

                # A stay is required but Tutu did not
                # return a usable hotel candidate.
                # This is not a complete trip.
                if hotel is None:
                    continue

            total_price = (
                out.price
                + back.price
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

            journey = JourneyOption(
                id=(
                    f"tutu:"
                    f"{out.id}:"
                    f"{back.id}:"
                    f"{hotel_id}"
                ),
                outbound=out,
                inbound=back,
                hotel=hotel,
                total_price=total_price,
            )

            journeys.append(
                journey
            )

        journeys.sort(
            key=lambda journey: (
                journey.total_price,
                journey.outbound.departure,
                journey.inbound.arrival,
            )
        )

        return journeys

    @staticmethod
    def _build_transport_pairs(
        *,
        outbound: list[TransportSegment],
        inbound: list[TransportSegment],
    ) -> list[
        tuple[
            TransportSegment,
            TransportSegment,
            StayKey | None,
        ]
    ]:

        result: list[
            tuple[
                TransportSegment,
                TransportSegment,
                StayKey | None,
            ]
        ] = []

        for out in outbound:
            for back in inbound:

                # Must already be in destination
                # before starting the return leg.
                if (
                    back.departure
                    <= out.arrival
                ):
                    continue

                stay_key = (
                    TutuMCPJourneyProvider
                    ._resolve_stay_key(
                        outbound=out,
                        inbound=back,
                    )
                )

                result.append(
                    (
                        out,
                        back,
                        stay_key,
                    )
                )

        return result

    @staticmethod
    def _resolve_stay_key(
        *,
        outbound: TransportSegment,
        inbound: TransportSegment,
    ) -> StayKey | None:

        check_in = (
            outbound.arrival.date()
        )

        check_out = (
            inbound.departure.date()
        )

        # Same-day trip:
        # no overnight stay required.
        if check_out <= check_in:
            return None

        return (
            check_in,
            check_out,
        )

    async def _load_hotels(
        self,
        *,
        city: str,
        stay_keys: set[StayKey],
        travelers: int,
    ) -> dict[
        StayKey,
        HotelOption,
    ]:

        if not stay_keys:
            return {}

        ordered_keys = sorted(
            stay_keys
        )

        tasks = [
            self.hotel_provider
            .get_cheapest_candidate(
                city=city,
                check_in=check_in,
                check_out=check_out,
                travelers=travelers,
            )
            for (
                check_in,
                check_out,
            ) in ordered_keys
        ]

        results = await asyncio.gather(
            *tasks,
            return_exceptions=True,
        )

        hotels: dict[
            StayKey,
            HotelOption,
        ] = {}

        for stay_key, result in zip(
            ordered_keys,
            results,
        ):
            # One failed hotel search must not
            # destroy other stay windows.
            if isinstance(
                result,
                BaseException,
            ):
                continue

            if result is None:
                continue

            hotels[stay_key] = result

        return hotels

    async def _search_direction(
        self,
        *,
        origin: str,
        destination: str,
        departure_date: str,
        travelers: int,
    ) -> list[TransportSegment]:

        payload = await self.client.call_tool(
            name="search_multitransport",
            arguments={
                "origin": origin,
                "destination": destination,
                "departure_date": (
                    departure_date
                ),
                "adults": travelers,
                "modes": [
                    "avia",
                    "railway",
                    "bus",
                    "etrain",
                ],
                "optimize_for": "price",
                "page": 1,
                "page_size": 30,
                "direct_only": False,
                "view": "compact",
            },
        )

        return (
            self.normalizer
            .normalize_search_result(
                payload=payload,
                travelers=travelers,
            )
        )