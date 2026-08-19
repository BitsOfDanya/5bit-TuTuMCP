from datetime import datetime, time, timedelta

from app.models.journey import (
    HotelOption,
    JourneyOption,
    TransportSegment,
)
from app.models.trip import TransportMode, TripSpec


class MockJourneyProvider:
    async def search_candidates(
        self,
        trip: TripSpec,
    ) -> list[JourneyOption]:

        outbound_after = trip.outbound_after or time(19, 0)
        return_before = trip.return_before or time(22, 0)

        outbound_base = datetime.combine(
            trip.outbound_date,
            outbound_after,
        )

        return_limit = datetime.combine(
            trip.return_date,
            return_before,
        )

        return [
            self._build_journey(
                trip=trip,
                journey_id="exact-expensive",
                outbound_departure=outbound_base + timedelta(minutes=15),
                inbound_arrival=return_limit - timedelta(minutes=30),
                total_price=22_000,
                outbound_mode=TransportMode.TRAIN,
                inbound_mode=TransportMode.TRAIN,
            ),
            self._build_journey(
                trip=trip,
                journey_id="leave-earlier",
                outbound_departure=outbound_base - timedelta(minutes=45),
                inbound_arrival=return_limit - timedelta(minutes=20),
                total_price=19_500,
                outbound_mode=TransportMode.TRAIN,
                inbound_mode=TransportMode.TRAIN,
            ),
            self._build_journey(
                trip=trip,
                journey_id="return-later",
                outbound_departure=outbound_base + timedelta(minutes=10),
                inbound_arrival=return_limit + timedelta(minutes=75),
                total_price=19_000,
                outbound_mode=TransportMode.TRAIN,
                inbound_mode=TransportMode.TRAIN,
            ),
            self._build_journey(
                trip=trip,
                journey_id="cheap-bus",
                outbound_departure=outbound_base + timedelta(minutes=20),
                inbound_arrival=return_limit - timedelta(minutes=40),
                total_price=16_800,
                outbound_mode=TransportMode.BUS,
                inbound_mode=TransportMode.BUS,
            ),
            self._build_journey(
                trip=trip,
                journey_id="fast-flight",
                outbound_departure=outbound_base + timedelta(minutes=40),
                inbound_arrival=return_limit - timedelta(minutes=90),
                total_price=26_000,
                outbound_mode=TransportMode.FLIGHT,
                inbound_mode=TransportMode.FLIGHT,
            ),
        ]

    def _build_journey(
        self,
        *,
        trip: TripSpec,
        journey_id: str,
        outbound_departure: datetime,
        inbound_arrival: datetime,
        total_price: int,
        outbound_mode: TransportMode,
        inbound_mode: TransportMode,
    ) -> JourneyOption:

        outbound_duration = {
            TransportMode.FLIGHT: timedelta(hours=2),
            TransportMode.TRAIN: timedelta(hours=11),
            TransportMode.BUS: timedelta(hours=13),
            TransportMode.SUBURBAN_TRAIN: timedelta(hours=4),
        }[outbound_mode]

        inbound_duration = {
            TransportMode.FLIGHT: timedelta(hours=2),
            TransportMode.TRAIN: timedelta(hours=11),
            TransportMode.BUS: timedelta(hours=13),
            TransportMode.SUBURBAN_TRAIN: timedelta(hours=4),
        }[inbound_mode]

        transport_price = int(total_price * 0.7)
        hotel_price = total_price - transport_price

        outbound_price = transport_price // 2
        inbound_price = transport_price - outbound_price

        return JourneyOption(
            id=journey_id,
            outbound=TransportSegment(
                id=f"{journey_id}-out",
                mode=outbound_mode,
                origin=trip.origin,
                destination=trip.destination,
                departure=outbound_departure,
                arrival=outbound_departure + outbound_duration,
                price=outbound_price,
                transfers=0,
            ),
            inbound=TransportSegment(
                id=f"{journey_id}-back",
                mode=inbound_mode,
                origin=trip.destination,
                destination=trip.origin,
                departure=inbound_arrival - inbound_duration,
                arrival=inbound_arrival,
                price=inbound_price,
                transfers=0,
            ),
            hotel=HotelOption(
                id=f"{journey_id}-hotel",
                name="Demo Hotel",
                price=hotel_price,
                rating=8.7,
            ),
            total_price=total_price,
        )