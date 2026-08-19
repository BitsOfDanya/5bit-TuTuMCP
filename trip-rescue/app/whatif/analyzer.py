from __future__ import annotations

from datetime import datetime

from app.models.journey import (
    HotelOption,
    JourneyOption,
    TransportSegment,
)
from app.models.rescue import (
    RescueComponent,
)
from app.whatif.models import (
    WhatIfCandidate,
    WhatIfImpact,
)


COMPONENT_ORDER: tuple[
    RescueComponent,
    ...,
] = (
    RescueComponent.OUTBOUND,
    RescueComponent.HOTEL,
    RescueComponent.INBOUND,
)


def build_whatif_impact(
    *,
    current: JourneyOption,
    candidate: JourneyOption,
) -> WhatIfImpact:
    changed = (
        changed_components(
            current=current,
            candidate=candidate,
        )
    )

    preserved = [
        component
        for component
        in _available_components(
            current
        )
        if component
        not in changed
    ]

    price_delta = (
        candidate.total_price
        - current.total_price
    )

    savings = max(
        0,
        -price_delta,
    )

    price_change_percent = (
        _price_change_percent(
            current_price=(
                current.total_price
            ),
            candidate_price=(
                candidate.total_price
            ),
        )
    )

    outbound_delta = (
        _minutes_between(
            current.outbound.departure,
            candidate.outbound.departure,
        )
    )

    inbound_delta = (
        _minutes_between(
            current.inbound.arrival,
            candidate.inbound.arrival,
        )
    )

    return WhatIfImpact(
        price_delta=price_delta,
        savings=savings,
        price_change_percent=(
            price_change_percent
        ),
        outbound_departure_delta_minutes=(
            outbound_delta
        ),
        inbound_arrival_delta_minutes=(
            inbound_delta
        ),
        components_changed=changed,
        components_preserved=preserved,
        disruption_count=len(
            changed
        ),
    )


def changed_components(
    *,
    current: JourneyOption,
    candidate: JourneyOption,
) -> list[
    RescueComponent
]:
    changed: list[
        RescueComponent
    ] = []

    if not _same_segment(
        current.outbound,
        candidate.outbound,
    ):
        changed.append(
            RescueComponent.OUTBOUND
        )

    if not _same_hotel(
        current.hotel,
        candidate.hotel,
    ):
        changed.append(
            RescueComponent.HOTEL
        )

    if not _same_segment(
        current.inbound,
        candidate.inbound,
    ):
        changed.append(
            RescueComponent.INBOUND
        )

    return [
        component
        for component
        in COMPONENT_ORDER
        if component
        in changed
    ]


def rank_whatif_candidates(
    *,
    current: JourneyOption,
    journeys: list[
        JourneyOption
    ],
    limit: int = 5,
) -> list[
    WhatIfCandidate
]:
    candidates = [
        WhatIfCandidate(
            id=journey.id,
            rank=1,
            journey=journey,
            impact=(
                build_whatif_impact(
                    current=current,
                    candidate=journey,
                )
            ),
        )
        for journey
        in journeys
    ]

    candidates.sort(
        key=_candidate_sort_key
    )

    ranked: list[
        WhatIfCandidate
    ] = []

    for index, candidate in enumerate(
        candidates[:limit],
        start=1,
    ):
        ranked.append(
            candidate.model_copy(
                deep=True,
                update={
                    "rank": index
                },
            )
        )

    return ranked


def journey_is_materially_same(
    left: JourneyOption,
    right: JourneyOption,
) -> bool:
    return (
        _same_segment(
            left.outbound,
            right.outbound,
        )
        and _same_hotel(
            left.hotel,
            right.hotel,
        )
        and _same_segment(
            left.inbound,
            right.inbound,
        )
    )


def _candidate_sort_key(
    candidate: WhatIfCandidate,
):
    """
    Decision-layer ranking.

    Priority:

    1. Change fewer accepted components.
    2. Pay less.
    3. Change schedule less.
    4. Stable deterministic ID ordering.

    This intentionally does NOT use Price Intelligence.
    Future ticket-price prediction belongs to the
    separate price module.
    """

    schedule_change = (
        abs(
            candidate
            .impact
            .outbound_departure_delta_minutes
        )
        + abs(
            candidate
            .impact
            .inbound_arrival_delta_minutes
        )
    )

    return (
        candidate.impact.disruption_count,
        candidate.journey.total_price,
        schedule_change,
        candidate.id,
    )


def _same_segment(
    left: TransportSegment,
    right: TransportSegment,
) -> bool:
    return (
        left.mode
        == right.mode

        and left.origin
        == right.origin

        and left.destination
        == right.destination

        and left.departure
        == right.departure

        and left.arrival
        == right.arrival

        and left.price
        == right.price

        and left.transfers
        == right.transfers
    )


def _same_hotel(
    left: HotelOption | None,
    right: HotelOption | None,
) -> bool:
    if (
        left is None
        and right is None
    ):
        return True

    if (
        left is None
        or right is None
    ):
        return False

    return (
        left.name
        == right.name

        and left.price
        == right.price

        and left.check_in
        == right.check_in

        and left.check_out
        == right.check_out
    )


def _available_components(
    journey: JourneyOption,
) -> list[
    RescueComponent
]:
    result = [
        RescueComponent.OUTBOUND
    ]

    if journey.hotel is not None:
        result.append(
            RescueComponent.HOTEL
        )

    result.append(
        RescueComponent.INBOUND
    )

    return result


def _minutes_between(
    old: datetime,
    new: datetime,
) -> int:
    """
    Journey data belongs to one trip-local timeline.

    For decision explanation we compare local wall-clock
    values and deliberately ignore timezone object identity.
    """

    old_local = old.replace(
        tzinfo=None
    )

    new_local = new.replace(
        tzinfo=None
    )

    seconds = (
        new_local
        - old_local
    ).total_seconds()

    return round(
        seconds / 60
    )


def _price_change_percent(
    *,
    current_price: int,
    candidate_price: int,
) -> float | None:
    if current_price <= 0:
        return None

    value = (
        (
            candidate_price
            - current_price
        )
        / current_price
        * 100
    )

    return round(
        value,
        2,
    )