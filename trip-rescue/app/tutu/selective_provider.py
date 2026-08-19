from __future__ import annotations

import asyncio

from datetime import timedelta

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


class TutuSelectiveProvider:
    """
    Low-level selective search for Trip Rescue.

    Unlike TutuMCPJourneyProvider this provider does NOT
    assemble a whole trip.

    It can independently search:
        - outbound transport;
        - inbound transport;
        - replacement hotel.

    This is exactly what Minimal Replan needs.
    """

    def __init__(
        self,
        *,
        client: TutuMCPClient | None = None,
        normalizer: TutuSearchNormalizer | None = None,
        hotel_provider: TutuHotelProvider | None = None,
        inbound_lookback_days: int = 1,
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

        self.inbound_lookback_days = max(
            inbound_lookback_days,
            0,
        )

    async def search_outbound(
        self,
        *,
        trip: TripSpec,
    ) -> list[TransportSegment]:
        """
        Search only the outbound direction.

        Outbound departure still has to start on
        trip.outbound_date.
        """

        return await self._search_direction(
            origin=trip.origin,
            destination=trip.destination,
            departure_date=(
                trip.outbound_date
                .isoformat()
            ),
            travelers=trip.travelers,
        )

    async def search_inbound(
        self,
        *,
        trip: TripSpec,
    ) -> list[TransportSegment]:
        """
        Search only the return direction.

        Important Rescue semantic:

        If user says:
            "23-го мне надо быть в Москве до 08:00"

        the valid transport may depart from destination
        on 22 August and arrive on 23 August.

        Therefore, when return_before exists, search both:
            return_date
            return_date - N days

        Default N = 1 for hackathon MVP.
        """

        dates = [
            trip.return_date,
        ]

        if (
            trip.return_before
            is not None
        ):
            for days_back in range(
                1,
                self.inbound_lookback_days + 1,
            ):
                dates.append(
                    trip.return_date
                    - timedelta(
                        days=days_back
                    )
                )

        tasks = [
            self._search_direction(
                origin=trip.destination,
                destination=trip.origin,
                departure_date=(
                    departure_date
                    .isoformat()
                ),
                travelers=trip.travelers,
            )
            for departure_date
            in dates
        ]

        results = await asyncio.gather(
            *tasks,
            return_exceptions=True,
        )

        segments: list[
            TransportSegment
        ] = []

        for result in results:
            if isinstance(
                result,
                BaseException,
            ):
                continue

            segments.extend(
                result
            )

        return _deduplicate_segments(
            segments
        )

    async def search_hotel(
        self,
        *,
        trip: TripSpec,
        current_journey: JourneyOption,
    ) -> HotelOption | None:
        """
        Search a replacement for the currently accepted
        hotel while keeping the same stay window.

        For a hotel-only budget rescue we do not need to
        touch transport at all.
        """

        current_hotel = (
            current_journey.hotel
        )

        if (
            current_hotel is not None
            and current_hotel.check_in
            is not None
            and current_hotel.check_out
            is not None
        ):
            check_in = (
                current_hotel.check_in
            )

            check_out = (
                current_hotel.check_out
            )

        else:
            check_in = (
                current_journey
                .outbound
                .arrival
                .date()
            )

            check_out = (
                current_journey
                .inbound
                .departure
                .date()
            )

        if check_out <= check_in:
            return None

        return await (
            self.hotel_provider
            .get_cheapest_candidate(
                city=trip.destination,
                check_in=check_in,
                check_out=check_out,
                travelers=trip.travelers,
            )
        )

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
                "page_size": 30,
            },
        )

        segments = (
            self.normalizer
            .normalize_search_result(
                payload=payload,
                travelers=travelers,
            )
        )

        segments.sort(
            key=lambda segment: (
                segment.price,
                segment.departure,
                segment.arrival,
            )
        )

        return segments


def _deduplicate_segments(
    segments: list[
        TransportSegment
    ],
) -> list[
    TransportSegment
]:
    result: list[
        TransportSegment
    ] = []

    seen: set[str] = set()

    for segment in segments:
        if segment.id in seen:
            continue

        seen.add(
            segment.id
        )

        result.append(
            segment
        )

    result.sort(
        key=lambda segment: (
            segment.price,
            segment.departure,
            segment.arrival,
        )
    )

    return result