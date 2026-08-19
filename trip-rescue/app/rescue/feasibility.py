from __future__ import annotations

from datetime import datetime

from app.models.journey import (
    JourneyOption,
)
from app.models.trip import (
    TripSpec,
)


def journey_satisfies_trip(
    *,
    trip: TripSpec,
    journey: JourneyOption,
) -> bool:
    """
    Final deterministic validation of a repaired journey.
    """

    outbound_departure = (
        _as_local_naive(
            journey.outbound.departure
        )
    )

    outbound_arrival = (
        _as_local_naive(
            journey.outbound.arrival
        )
    )

    inbound_departure = (
        _as_local_naive(
            journey.inbound.departure
        )
    )

    inbound_arrival = (
        _as_local_naive(
            journey.inbound.arrival
        )
    )

    # ---------------------------------------------------------
    # Outbound calendar date
    # ---------------------------------------------------------

    if (
        outbound_departure.date()
        != trip.outbound_date
    ):
        return False

    # ---------------------------------------------------------
    # Return semantics
    # ---------------------------------------------------------

    if trip.return_before is None:
        # Old/default semantics:
        # return journey starts on requested return date.
        if (
            inbound_departure.date()
            != trip.return_date
        ):
            return False

    else:
        # Deadline semantics:
        #
        # "23-го быть в Москве до 08:00"
        #
        # A train leaving on the evening of the 22nd
        # is completely valid.
        return_deadline = (
            datetime.combine(
                trip.return_date,
                trip.return_before,
            )
        )

        if (
            inbound_arrival
            > return_deadline
        ):
            return False

    # ---------------------------------------------------------
    # Chronology
    # ---------------------------------------------------------

    if (
        outbound_arrival
        >= inbound_departure
    ):
        return False

    if (
        journey.outbound.arrival
        <= journey.outbound.departure
    ):
        return False

    if (
        journey.inbound.arrival
        <= journey.inbound.departure
    ):
        return False

    # ---------------------------------------------------------
    # Outbound lower bound
    # ---------------------------------------------------------

    if trip.outbound_after is not None:
        required_departure = (
            datetime.combine(
                trip.outbound_date,
                trip.outbound_after,
            )
        )

        if (
            outbound_departure
            < required_departure
        ):
            return False

    # ---------------------------------------------------------
    # Budget
    # ---------------------------------------------------------

    if (
        trip.budget is not None
        and journey.total_price
        > trip.budget
    ):
        return False

    # ---------------------------------------------------------
    # Excluded transport
    # ---------------------------------------------------------

    excluded = set(
        trip.excluded_transport
    )

    if (
        journey.outbound.mode
        in excluded
    ):
        return False

    if (
        journey.inbound.mode
        in excluded
    ):
        return False

    # ---------------------------------------------------------
    # Transfers
    # ---------------------------------------------------------

    if trip.max_transfers is not None:
        if (
            journey.outbound.transfers
            > trip.max_transfers
        ):
            return False

        if (
            journey.inbound.transfers
            > trip.max_transfers
        ):
            return False

    # ---------------------------------------------------------
    # Hotel
    # ---------------------------------------------------------

    hotel = journey.hotel

    if hotel is not None:
        if (
            hotel.check_in is not None
            and hotel.check_out is not None
            and hotel.check_out
            <= hotel.check_in
        ):
            return False

        # The hotel cannot start only after the user has
        # already left the destination.
        #
        # BUT checkout may be later than actual departure:
        # an accepted reservation can simply be left early.
        if (
            hotel.check_in is not None
            and hotel.check_in
            > inbound_departure.date()
        ):
            return False

    return True


def _as_local_naive(
    value: datetime,
) -> datetime:
    return value.replace(
        tzinfo=None
    )