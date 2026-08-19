from typing import Any

from pydantic import ValidationError

from app.domain.search import (
    SearchHotel,
    SearchOption,
    SearchOptionKind,
    SearchSegment,
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
