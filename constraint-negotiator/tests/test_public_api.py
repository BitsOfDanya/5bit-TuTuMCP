from datetime import datetime

from app.api.mapper import (
    to_public_result,
)
from app.models.journey import (
    HotelOption,
    JourneyOption,
    TransportSegment,
)
from app.models.relaxation import (
    NegotiationResult,
    RelaxationPlan,
    RelaxationSummary,
)
from app.models.trip import (
    TransportMode,
    TripSpec,
)


def test_public_result_hides_internal_mcp_refs() -> None:

    trip = TripSpec(
        origin="Москва",
        destination="Казань",
        outbound_date="2026-08-21",
        return_date="2026-08-23",
        travelers=2,
        budget=20_000,
    )

    outbound = TransportSegment(
        id="out",
        mode=TransportMode.FLIGHT,
        origin="Москва",
        destination="Казань",
        departure=datetime.fromisoformat(
            "2026-08-21T21:00:00+03:00"
        ),
        arrival=datetime.fromisoformat(
            "2026-08-21T22:30:00+03:00"
        ),
        price=10_000,
        carrier="Carrier",
        booking_url=(
            "https://example.com/out"
        ),
        checkout_ref={
            "offer_hash": "SECRET_INTERNAL_REF"
        },
        details_ref={
            "internal": "value"
        },
    )

    inbound = TransportSegment(
        id="back",
        mode=TransportMode.FLIGHT,
        origin="Казань",
        destination="Москва",
        departure=datetime.fromisoformat(
            "2026-08-23T18:00:00+03:00"
        ),
        arrival=datetime.fromisoformat(
            "2026-08-23T20:00:00+03:00"
        ),
        price=10_000,
        booking_url=(
            "https://example.com/back"
        ),
    )

    hotel = HotelOption(
        id="hotel",
        name="Hotel",
        price=5_000,
        nights=2,
        booking_url=(
            "https://example.com/hotel"
        ),
        checkout_ref={
            "offerpack_hash": "INTERNAL"
        },
    )

    journey = JourneyOption(
        id="journey",
        outbound=outbound,
        inbound=inbound,
        hotel=hotel,
        total_price=25_000,
    )

    plan = RelaxationPlan(
        id="plan",
        kind="single",
        changes=[],
        score=0.5,
        new_trip_spec=trip,
        journey=journey,
        summary=RelaxationSummary(
            headline="Test",
            explanation="Test",
            total_price=25_000,
            transport_price=20_000,
            hotel_price=5_000,
            outbound_label="Самолёт",
            inbound_label="Самолёт",
            hotel_label="Hotel",
        ),
    )

    result = NegotiationResult(
        status="negotiation_required",
        trip_spec=trip,
        alternatives=[
            plan
        ],
    )

    public = to_public_result(
        result
    )

    payload = (
        public.model_dump(
            mode="json"
        )
    )

    serialized = str(
        payload
    )

    assert (
        "checkout_ref"
        not in serialized
    )

    assert (
        "details_ref"
        not in serialized
    )

    assert (
        "SECRET_INTERNAL_REF"
        not in serialized
    )

    assert (
        public.alternatives[0]
        .journey
        .outbound
        .booking_url
        == "https://example.com/out"
    )