from typing import Any

from pydantic import ValidationError

from app.domain.search import (
    SearchHotel,
    SearchOption,
    SearchOptionKind,
    SearchSegment,
    TrackingHotel,
    TrackingJourney,
    TrackingPayload,
    TrackingSegment,
    TrackingTripSpec,
)


def build_search_options(
    negotiation: dict[str, Any] | None,
    fallback_url: str | None,
) -> list[SearchOption]:
    if not negotiation:
        return []

    direct_options = negotiation.get("options")
    if isinstance(direct_options, list):
        options: list[SearchOption] = []
        for item in direct_options[:3]:
            if not isinstance(item, dict):
                continue
            try:
                options.append(SearchOption.model_validate(item))
            except ValidationError:
                continue
        return options

    default_title = _trip_title(negotiation.get("trip_spec"))
    options = [
        option
        for journey in negotiation.get("journeys", [])
        if isinstance(journey, dict)
        and (
            option := _build_option(
                journey,
                SearchOptionKind.JOURNEY,
                fallback_url,
                default_title=default_title,
                trip_spec=negotiation.get("trip_spec"),
            )
        )
        is not None
    ]
    options.extend(
        option
        for alternative in negotiation.get("alternatives", [])
        if isinstance(alternative, dict)
        and isinstance(alternative.get("journey"), dict)
        and (
            option := _build_option(
                alternative["journey"],
                SearchOptionKind.RELAXATION,
                fallback_url,
                alternative,
                default_title,
                alternative.get("new_trip_spec") or negotiation.get("trip_spec"),
            )
        )
        is not None
    )
    return options[:3]


def _build_option(
    journey: dict[str, Any],
    kind: SearchOptionKind,
    fallback_url: str | None,
    alternative: dict[str, Any] | None = None,
    default_title: str | None = None,
    trip_spec: Any = None,
) -> SearchOption | None:
    outbound = _segment(journey.get("outbound"))
    inbound = _segment(journey.get("inbound"))
    total_price = journey.get("total_price")
    if outbound is None or inbound is None or not isinstance(total_price, int):
        return None

    summary = alternative.get("summary", {}) if alternative else {}
    if not isinstance(summary, dict):
        summary = {}
    changes = _change_labels(alternative.get("changes", [])) if alternative else []
    title = summary.get("headline")
    if not isinstance(title, str) or not title.strip():
        title = default_title or f"{outbound.origin} — {outbound.destination}"
    explanation = summary.get("explanation")
    if not isinstance(explanation, str):
        explanation = None

    try:
        return SearchOption(
            id=str(journey.get("id") or alternative and alternative.get("id") or title),
            kind=kind,
            title=title,
            explanation=explanation,
            total_price=total_price,
            currency=_currency(journey),
            outbound=outbound,
            inbound=inbound,
            hotel=_hotel(journey.get("hotel")),
            changes=changes,
            action_url=_action_url(journey) or fallback_url,
            tracking_payload=_tracking_payload(journey, trip_spec),
        )
    except ValidationError:
        return None


def _segment(payload: Any) -> SearchSegment | None:
    if not isinstance(payload, dict):
        return None
    required = ("mode", "origin", "destination", "departure", "arrival", "price")
    if any(payload.get(field) is None for field in required):
        return None
    try:
        return SearchSegment.model_validate(payload)
    except ValidationError:
        return None


def _hotel(payload: Any) -> SearchHotel | None:
    if not isinstance(payload, dict) or not payload.get("name"):
        return None
    try:
        return SearchHotel.model_validate(payload)
    except ValidationError:
        return None


def _currency(journey: dict[str, Any]) -> str:
    for part in (journey.get("outbound"), journey.get("inbound"), journey.get("hotel")):
        if isinstance(part, dict) and isinstance(part.get("currency"), str):
            return part["currency"].upper()
    return "RUB"


def _action_url(journey: dict[str, Any]) -> str | None:
    for part_name in ("outbound", "inbound", "hotel"):
        part = journey.get(part_name)
        if not isinstance(part, dict):
            continue
        for field in ("booking_url", "search_results_url"):
            value = part.get(field)
            if isinstance(value, str) and value.strip():
                return value
    return None


def _tracking_payload(journey: dict[str, Any], raw_spec: Any) -> TrackingPayload | None:
    outbound = journey.get("outbound")
    inbound = journey.get("inbound")
    if not isinstance(outbound, dict) or not isinstance(inbound, dict):
        return None
    spec = raw_spec if isinstance(raw_spec, dict) else {}
    outbound_date = _date_value(spec.get("outbound_date"), outbound.get("departure"))
    return_date = _date_value(spec.get("return_date"), inbound.get("departure"))
    if outbound_date is None or return_date is None:
        return None

    hotel_payload = journey.get("hotel")
    hotel = _tracking_hotel(hotel_payload)
    outbound_price = _non_negative_int(outbound.get("price"))
    inbound_price = _non_negative_int(inbound.get("price"))
    if outbound_price is None or inbound_price is None:
        return None
    transport_price = _non_negative_int(journey.get("transport_price"))
    if transport_price is None:
        transport_price = outbound_price + inbound_price
    hotel_price = _non_negative_int(journey.get("hotel_price"))
    if hotel_price is None:
        hotel_price = hotel.price if hotel is not None else 0

    try:
        return TrackingPayload(
            trip_spec=TrackingTripSpec(
                origin=_text(spec.get("origin")) or _text(outbound.get("origin")) or "",
                destination=(
                    _text(spec.get("destination"))
                    or _text(outbound.get("destination"))
                    or ""
                ),
                outbound_date=outbound_date,
                return_date=return_date,
                travelers=_positive_int(spec.get("travelers")) or 1,
                budget=_positive_int(spec.get("budget")),
                max_transfers=_non_negative_int(spec.get("max_transfers")),
            ),
            journeys=[
                TrackingJourney(
                    id=str(journey.get("id") or "selected-journey"),
                    total_price=journey["total_price"],
                    transport_price=transport_price,
                    hotel_price=hotel_price,
                    outbound=TrackingSegment.model_validate(_tracking_segment(outbound)),
                    inbound=TrackingSegment.model_validate(_tracking_segment(inbound)),
                    hotel=hotel,
                )
            ],
        )
    except (KeyError, ValidationError):
        return None


def _tracking_segment(segment: dict[str, Any]) -> dict[str, Any]:
    return {
        "mode": segment.get("mode"),
        "origin": segment.get("origin"),
        "destination": segment.get("destination"),
        "departure": segment.get("departure"),
        "arrival": segment.get("arrival"),
        "price": segment.get("price"),
        "duration_minutes": segment.get("duration_minutes"),
        "transfers": segment.get("transfers", 0),
        "carrier": segment.get("carrier"),
        "booking_url": segment.get("booking_url") or segment.get("search_results_url"),
    }


def _tracking_hotel(payload: Any) -> TrackingHotel | None:
    if not isinstance(payload, dict) or not _text(payload.get("name")):
        return None
    try:
        return TrackingHotel(
            name=payload["name"],
            price=payload.get("price", 0),
            rating=payload.get("rating"),
            booking_url=payload.get("booking_url"),
        )
    except (KeyError, ValidationError):
        return None


def _date_value(primary: Any, fallback_datetime: Any) -> str | None:
    for value in (primary, fallback_datetime):
        if isinstance(value, str) and len(value) >= 10:
            return value[:10]
    return None


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _positive_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def _non_negative_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _change_labels(changes: Any) -> list[str]:
    if not isinstance(changes, list):
        return []
    labels: list[str] = []
    for change in changes:
        if not isinstance(change, dict):
            continue
        title = change.get("title")
        description = change.get("description")
        if isinstance(title, str) and title.strip():
            labels.append(title)
        elif isinstance(description, str) and description.strip():
            labels.append(description)
    return labels


def _trip_title(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    origin = payload.get("origin")
    destination = payload.get("destination")
    if not isinstance(origin, str) or not isinstance(destination, str):
        return None
    return f"{origin} — {destination}"
