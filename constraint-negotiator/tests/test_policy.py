from datetime import datetime

from app.models.journey import (
    HotelOption,
    JourneyOption,
    TransportSegment,
)
from app.models.trip import (
    ConstraintField,
    TransportMode,
    TripSpec,
)
from app.negotiator.solver import (
    ConstraintNegotiator,
)


def test_unreasonable_return_shift_is_filtered() -> None:
    trip = TripSpec(
        origin="Москва",
        destination="Казань",
        outbound_date="2026-08-21",
        return_date="2026-08-23",
        outbound_after="19:00:00",
        return_before="22:00:00",
        travelers=2,
        budget=20_000,
        excluded_transport=[
            TransportMode.BUS,
        ],
    )

    outbound = TransportSegment(
        id="bus-out",
        mode=TransportMode.BUS,
        origin="Москва",
        destination="Казань",
        departure=datetime.fromisoformat(
            "2026-08-21T22:45:00+03:00"
        ),
        arrival=datetime.fromisoformat(
            "2026-08-22T08:45:00+03:00"
        ),
        price=5_000,
    )

    inbound = TransportSegment(
        id="bus-back",
        mode=TransportMode.BUS,
        origin="Казань",
        destination="Москва",
        departure=datetime.fromisoformat(
            "2026-08-23T16:00:00+03:00"
        ),
        arrival=datetime.fromisoformat(
            "2026-08-24T06:00:00+03:00"
        ),
        price=9_134,
    )

    hotel = HotelOption(
        id="hotel",
        name="Test Hotel",
        price=3_275,
        nights=1,
    )

    journey = JourneyOption(
        id="bad-time-combination",
        outbound=outbound,
        inbound=inbound,
        hotel=hotel,
        total_price=17_409,
    )

    solver = ConstraintNegotiator()

    result = solver.solve(
        trip=trip,
        journeys=[
            journey,
        ],
    )

    assert (
        result.status
        == "no_options"
    )

    assert (
        result.alternatives
        == []
    )


def test_combination_has_frontend_summary() -> None:
    trip = TripSpec(
        origin="Москва",
        destination="Казань",
        outbound_date="2026-08-21",
        return_date="2026-08-23",
        outbound_after="19:00:00",
        return_before="22:00:00",
        travelers=2,
        budget=20_000,
        excluded_transport=[
            TransportMode.BUS,
        ],
    )

    outbound = TransportSegment(
        id="bus-out",
        mode=TransportMode.BUS,
        origin="Москва",
        destination="Казань",
        departure=datetime.fromisoformat(
            "2026-08-21T22:45:00+03:00"
        ),
        arrival=datetime.fromisoformat(
            "2026-08-22T08:45:00+03:00"
        ),
        price=5_000,
        carrier="Евротранс",
    )

    inbound = TransportSegment(
        id="flight-back",
        mode=TransportMode.FLIGHT,
        origin="Казань",
        destination="Москва",
        departure=datetime.fromisoformat(
            "2026-08-23T07:05:00+03:00"
        ),
        arrival=datetime.fromisoformat(
            "2026-08-23T08:40:00+03:00"
        ),
        price=14_428,
        carrier="Аэрофлот",
        voyage_no="SU-1199",
    )

    hotel = HotelOption(
        id="hotel",
        name="Гостевой Дом Мансарда",
        price=3_275,
        nights=1,
    )

    journey = JourneyOption(
        id="good-combination",
        outbound=outbound,
        inbound=inbound,
        hotel=hotel,
        total_price=22_703,
    )

    solver = ConstraintNegotiator()

    result = solver.solve(
        trip=trip,
        journeys=[
            journey,
        ],
    )

    assert (
        result.status
        == "negotiation_required"
    )

    assert len(
        result.alternatives
    ) == 1

    plan = (
        result.alternatives[0]
    )

    assert (
        plan.kind
        == "combination"
    )

    fields = {
        change.field
        for change
        in plan.changes
    }

    assert fields == {
        ConstraintField.BUDGET,
        ConstraintField.TRANSPORT,
    }

    assert (
        plan.summary
        is not None
    )

    assert (
        plan.summary.total_price
        == 22_703
    )

    assert (
        plan.summary.transport_price
        == 19_428
    )

    assert (
        plan.summary.hotel_price
        == 3_275
    )

    assert (
        "автобус"
        in plan.summary.headline.lower()
    )

    assert (
        "2 703"
        in plan.summary.headline
    )

    assert (
        plan.summary.outbound_label
        == "Автобус · Евротранс"
    )

    assert (
        plan.summary.inbound_label
        == "Самолёт · Аэрофлот · SU-1199"
    )

    assert (
        plan.summary.hotel_label
        == "Гостевой Дом Мансарда · 1 ночь"
    )