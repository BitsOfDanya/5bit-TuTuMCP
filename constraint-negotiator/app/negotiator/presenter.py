from __future__ import annotations

from typing import Any

from app.models.journey import (
    JourneyOption,
    TransportSegment,
)
from app.models.relaxation import (
    ConstraintChange,
    RelaxationSummary,
)
from app.models.trip import (
    ConstraintField,
    TransportMode,
)


TRANSPORT_LABELS: dict[
    TransportMode,
    str,
] = {
    TransportMode.FLIGHT: "Самолёт",
    TransportMode.TRAIN: "Поезд",
    TransportMode.BUS: "Автобус",
    TransportMode.SUBURBAN_TRAIN: "Электричка",
}


RAW_TRANSPORT_LABELS: dict[
    str,
    str,
] = {
    "flight": "самолёт",
    "train": "поезд",
    "bus": "автобус",
    "suburban_train": "электричку",
}


def build_relaxation_summary(
    *,
    journey: JourneyOption,
    changes: list[ConstraintChange],
) -> RelaxationSummary:

    headline = " + ".join(
        _change_label(change)
        for change in _ordered_changes(
            changes
        )
    )

    transport_price = (
        journey.outbound.price
        + journey.inbound.price
    )

    hotel_price = (
        journey.hotel.price
        if journey.hotel is not None
        else 0
    )

    if journey.hotel is not None:
        explanation = (
            "Вся поездка становится возможной "
            f"за {_format_money(journey.total_price)} ₽ "
            "с учётом транспорта и проживания."
        )
    else:
        explanation = (
            "Поездка становится возможной "
            f"за {_format_money(journey.total_price)} ₽."
        )

    return RelaxationSummary(
        headline=headline,
        explanation=explanation,
        total_price=journey.total_price,
        transport_price=transport_price,
        hotel_price=hotel_price,
        outbound_label=(
            _segment_label(
                journey.outbound
            )
        ),
        inbound_label=(
            _segment_label(
                journey.inbound
            )
        ),
        hotel_label=(
            _hotel_label(
                journey
            )
        ),
    )


def _ordered_changes(
    changes: list[ConstraintChange],
) -> list[ConstraintChange]:

    priority = {
        ConstraintField.TRANSPORT: 0,
        ConstraintField.OUTBOUND_AFTER: 1,
        ConstraintField.RETURN_BEFORE: 2,
        ConstraintField.MAX_TRANSFERS: 3,
        ConstraintField.BUDGET: 4,
    }

    return sorted(
        changes,
        key=lambda change: priority.get(
            change.field,
            100,
        ),
    )


def _change_label(
    change: ConstraintChange,
) -> str:

    if (
        change.field
        == ConstraintField.BUDGET
    ):
        # change.title already looks like:
        # "+2 703 ₽"
        #
        # Since labels are joined with " + ",
        # remove the leading plus here:
        #
        # "Разрешить автобус + 2 703 ₽ к бюджету"
        clean_title = (
            change.title
            .lstrip("+")
            .strip()
        )

        return (
            f"{clean_title} "
            "к бюджету"
        )

    if (
        change.field
        == ConstraintField.TRANSPORT
    ):
        transport = (
            _transport_change_label(
                change.new_value
            )
        )

        return (
            f"Разрешить {transport}"
        )

    if (
        change.field
        == ConstraintField.OUTBOUND_AFTER
    ):
        return change.description

    if (
        change.field
        == ConstraintField.RETURN_BEFORE
    ):
        return change.description

    if (
        change.field
        == ConstraintField.MAX_TRANSFERS
    ):
        return change.description

    return change.title


def _transport_change_label(
    value: Any,
) -> str:

    if isinstance(
        value,
        list,
    ):
        raw_values = [
            str(item)
            for item in value
        ]

    elif isinstance(
        value,
        str,
    ):
        raw_values = [
            item.strip()
            for item in value.split(",")
            if item.strip()
        ]

    else:
        return "другой транспорт"

    labels = [
        RAW_TRANSPORT_LABELS.get(
            item,
            item,
        )
        for item in raw_values
    ]

    if not labels:
        return "другой транспорт"

    return ", ".join(
        labels
    )


def _segment_label(
    segment: TransportSegment,
) -> str:

    transport = (
        TRANSPORT_LABELS.get(
            segment.mode,
            segment.mode.value,
        )
    )

    parts = [
        transport
    ]

    if segment.carrier:
        parts.append(
            segment.carrier
        )

    if segment.voyage_no:
        parts.append(
            segment.voyage_no
        )

    return " · ".join(
        parts
    )


def _hotel_label(
    journey: JourneyOption,
) -> str | None:

    hotel = journey.hotel

    if hotel is None:
        return None

    if hotel.nights is None:
        return hotel.name

    return (
        f"{hotel.name} · "
        f"{hotel.nights} "
        f"{_night_word(hotel.nights)}"
    )


def _night_word(
    nights: int,
) -> str:

    if (
        nights % 10 == 1
        and nights % 100 != 11
    ):
        return "ночь"

    if (
        nights % 10 in {2, 3, 4}
        and nights % 100
        not in {12, 13, 14}
    ):
        return "ночи"

    return "ночей"


def _format_money(
    value: int,
) -> str:

    return (
        f"{value:,}"
        .replace(",", " ")
    )