from __future__ import annotations

from app.api.schemas import (
    CurrentJourneyInput,
    PublicHotelOption,
    PublicJourneyOption,
    PublicRescueCandidate,
    PublicRescueInsight,
    PublicRescueRelaxation,
    PublicRescueResponse,
    PublicTransportSegment,
    RawRescueResponse,
    RescueCandidateSummary,
)
from app.models.journey import (
    HotelOption,
    JourneyOption,
    TransportSegment,
)
from app.models.rescue import (
    RescueCandidate,
    RescueComponent,
)
from app.rescue.insights import (
    build_rescue_insights,
)


def to_domain_journey(
    value: CurrentJourneyInput,
) -> JourneyOption:
    outbound = TransportSegment(
        id=(
            value.outbound.id
            or f"{value.id}:outbound"
        ),
        mode=value.outbound.mode,
        origin=value.outbound.origin,
        destination=(
            value.outbound.destination
        ),
        departure=(
            value.outbound.departure
        ),
        arrival=value.outbound.arrival,
        price=value.outbound.price,
        duration_minutes=(
            value.outbound.duration_minutes
        ),
        transfers=(
            value.outbound.transfers
        ),
        carrier=(
            value.outbound.carrier
        ),
        voyage_no=(
            value.outbound.voyage_no
        ),
        rating=value.outbound.rating,
        review_count=(
            value.outbound.review_count
        ),
        booking_url=(
            value.outbound.booking_url
        ),
    )

    inbound = TransportSegment(
        id=(
            value.inbound.id
            or f"{value.id}:inbound"
        ),
        mode=value.inbound.mode,
        origin=value.inbound.origin,
        destination=(
            value.inbound.destination
        ),
        departure=(
            value.inbound.departure
        ),
        arrival=value.inbound.arrival,
        price=value.inbound.price,
        duration_minutes=(
            value.inbound.duration_minutes
        ),
        transfers=(
            value.inbound.transfers
        ),
        carrier=value.inbound.carrier,
        voyage_no=(
            value.inbound.voyage_no
        ),
        rating=value.inbound.rating,
        review_count=(
            value.inbound.review_count
        ),
        booking_url=(
            value.inbound.booking_url
        ),
    )

    hotel = None

    if value.hotel is not None:
        hotel = HotelOption(
            id=(
                value.hotel.id
                or f"{value.id}:hotel"
            ),
            name=value.hotel.name,
            price=value.hotel.price,
            stars=value.hotel.stars,
            rating=value.hotel.rating,
            review_count=(
                value.hotel.review_count
            ),
            address=value.hotel.address,
            room_name=value.hotel.room_name,
            check_in=value.hotel.check_in,
            check_out=value.hotel.check_out,
            nights=value.hotel.nights,
            booking_url=(
                value.hotel.booking_url
            ),
            photo_url=(
                value.hotel.photo_url
            ),
        )

    total_price = (
        outbound.price
        + inbound.price
        + (
            hotel.price
            if hotel is not None
            else 0
        )
    )

    return JourneyOption(
        id=value.id,
        outbound=outbound,
        inbound=inbound,
        hotel=hotel,
        total_price=total_price,
    )


def to_public_response(
    result: RawRescueResponse,
) -> PublicRescueResponse:
    reasons: list[str] = []

    for component in (
        result.validation.components
    ):
        reasons.extend(
            reason.message
            for reason
            in component.reasons
        )

    reasons.extend(
        reason.message
        for reason
        in result.validation.global_reasons
    )

    return PublicRescueResponse(
        status=result.status,
        updated_trip=(
            result.updated_trip
        ),
        changed_fields=(
            result.diff.changed_fields
        ),
        preserved_components=(
            result.validation
            .preserved_components
        ),
        replace_components=(
            result.validation
            .replace_components
        ),
        reasons=reasons,
        candidates=[
            _to_public_candidate(
                candidate
            )
            for candidate
            in result.execution.candidates
        ],
    )


def _to_public_candidate(
    candidate: RescueCandidate,
) -> PublicRescueCandidate:
    raw_insights = (
        build_rescue_insights(
            journey=(
                candidate.journey
            )
        )
    )

    insights = [
        PublicRescueInsight(
            type=insight.type.value,
            severity=(
                insight.severity.value
            ),
            title=insight.title,
            description=(
                insight.description
            ),
            component=(
                insight.component
            ),
            action=(
                insight.action.value
                if insight.action
                is not None
                else None
            ),
            estimated_amount=(
                insight.estimated_amount
            ),
            estimated_unused_nights=(
                insight
                .estimated_unused_nights
            ),
        )
        for insight
        in raw_insights
    ]

    relaxations = [
        PublicRescueRelaxation(
            field=relaxation.field,
            title=relaxation.title,
            description=(
                relaxation.description
            ),
            old_value=(
                relaxation.old_value
            ),
            new_value=(
                relaxation.new_value
            ),
            magnitude=(
                relaxation.magnitude
            ),
            score=(
                relaxation.score
            ),
        )
        for relaxation
        in candidate.relaxations
    ]

    return PublicRescueCandidate(
        id=candidate.id,
        replaced_components=(
            candidate.replaced_components
        ),
        preserved_components=(
            candidate.preserved_components
        ),
        score=candidate.score,
        exact=candidate.exact,
        relaxations=relaxations,
        suggested_trip=(
            candidate.suggested_trip
        ),
        summary=(
            _candidate_summary(
                candidate
            )
        ),
        insights=insights,
        journey=(
            _to_public_journey(
                candidate.journey
            )
        ),
    )


def _candidate_summary(
    candidate: RescueCandidate,
) -> RescueCandidateSummary:

    if not candidate.exact:
        relaxation_titles = (
            " + ".join(
                relaxation.title
                for relaxation
                in candidate.relaxations
            )
        )

        headline = (
            "Есть ближайший компромисс"
        )

        explanation = (
            "Точный вариант не найден. "
            "Можно сохранить обязательные "
            "условия поездки, если: "
            f"{relaxation_titles}."
        )

        return RescueCandidateSummary(
            headline=headline,
            explanation=explanation,
            price_delta_label=(
                _price_delta_label(
                    candidate.price_delta
                )
            ),
            previous_total_price=(
                candidate
                .previous_total_price
            ),
            new_total_price=(
                candidate
                .new_total_price
            ),
        )

    replaced = " и ".join(
        _component_label(
            component
        )
        for component
        in candidate.replaced_components
    )

    preserved = " и ".join(
        _component_label(
            component
        )
        for component
        in candidate.preserved_components
    )

    if (
        len(
            candidate.replaced_components
        )
        == 1
    ):
        headline = (
            f"Меняем только {replaced}"
        )
    else:
        headline = (
            f"Меняем {replaced}"
        )

    if preserved:
        explanation = (
            f"Сохраняем {preserved}. "
            "Остальная часть поездки "
            "не пересобирается."
        )
    else:
        explanation = (
            "Изменение требует "
            "пересобрать всю поездку."
        )

    return RescueCandidateSummary(
        headline=headline,
        explanation=explanation,
        price_delta_label=(
            _price_delta_label(
                candidate.price_delta
            )
        ),
        previous_total_price=(
            candidate.previous_total_price
        ),
        new_total_price=(
            candidate.new_total_price
        ),
    )


def _to_public_journey(
    journey: JourneyOption,
) -> PublicJourneyOption:
    return PublicJourneyOption(
        id=journey.id,
        total_price=(
            journey.total_price
        ),
        transport_price=(
            journey.transport_price
        ),
        hotel_price=(
            journey.hotel_price
        ),
        outbound=(
            _to_public_segment(
                journey.outbound
            )
        ),
        inbound=(
            _to_public_segment(
                journey.inbound
            )
        ),
        hotel=(
            _to_public_hotel(
                journey.hotel
            )
            if journey.hotel
            is not None
            else None
        ),
    )


def _to_public_segment(
    segment: TransportSegment,
) -> PublicTransportSegment:
    return PublicTransportSegment(
        mode=segment.mode,
        origin=segment.origin,
        destination=(
            segment.destination
        ),
        departure=segment.departure,
        arrival=segment.arrival,
        price=segment.price,
        duration_minutes=(
            segment.duration_minutes
        ),
        transfers=segment.transfers,
        carrier=segment.carrier,
        voyage_no=segment.voyage_no,
        rating=segment.rating,
        review_count=(
            segment.review_count
        ),
        booking_url=(
            segment.booking_url
        ),
    )


def _to_public_hotel(
    hotel: HotelOption,
) -> PublicHotelOption:
    return PublicHotelOption(
        name=hotel.name,
        price=hotel.price,
        stars=hotel.stars,
        rating=hotel.rating,
        review_count=(
            hotel.review_count
        ),
        address=hotel.address,
        room_name=hotel.room_name,
        check_in=hotel.check_in,
        check_out=hotel.check_out,
        nights=hotel.nights,
        booking_url=(
            hotel.booking_url
        ),
        photo_url=(
            hotel.photo_url
        ),
    )


def _component_label(
    component: RescueComponent,
) -> str:
    labels = {
        RescueComponent.OUTBOUND: (
            "дорогу туда"
        ),
        RescueComponent.HOTEL: (
            "отель"
        ),
        RescueComponent.INBOUND: (
            "дорогу обратно"
        ),
    }

    return labels[
        component
    ]


def _price_delta_label(
    value: int,
) -> str:
    if value == 0:
        return (
            "Без изменения цены"
        )

    formatted = (
        f"{abs(value):,}"
        .replace(",", " ")
    )

    if value > 0:
        return (
            f"+{formatted} ₽"
        )

    return (
        f"−{formatted} ₽"
    )