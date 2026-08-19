from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.models.journey import JourneyOption
from app.models.rescue import RescueComponent


class InsightType(str, Enum):
    HOTEL_UNUSED_NIGHTS = "hotel_unused_nights"


class InsightSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"


class InsightAction(str, Enum):
    SEARCH_SHORTER_HOTEL = "search_shorter_hotel"


@dataclass(
    frozen=True,
    slots=True,
)
class RescueInsight:
    type: InsightType
    severity: InsightSeverity

    title: str
    description: str

    component: RescueComponent | None = None

    action: InsightAction | None = None

    estimated_amount: int | None = None
    estimated_unused_nights: int | None = None


def build_rescue_insights(
    *,
    journey: JourneyOption,
) -> list[RescueInsight]:
    """
    Analyze side effects of a rescued journey.

    These are NOT feasibility errors.

    The journey may be perfectly valid while still having
    consequences worth surfacing to the user.
    """

    insights: list[
        RescueInsight
    ] = []

    hotel_insight = (
        _build_unused_hotel_insight(
            journey=journey
        )
    )

    if hotel_insight is not None:
        insights.append(
            hotel_insight
        )

    return insights


def _build_unused_hotel_insight(
    *,
    journey: JourneyOption,
) -> RescueInsight | None:
    hotel = journey.hotel

    if hotel is None:
        return None

    if (
        hotel.check_in is None
        or hotel.check_out is None
    ):
        return None

    if (
        hotel.check_out
        <= hotel.check_in
    ):
        return None

    departure = (
        journey.inbound.departure
    )

    departure_date = (
        departure.date()
    )

    # User leaves on or after planned checkout.
    if (
        departure_date
        >= hotel.check_out
    ):
        return None

    booked_nights = (
        hotel.nights
        if hotel.nights is not None
        else (
            hotel.check_out
            - hotel.check_in
        ).days
    )

    if booked_nights <= 0:
        return None

    # Nights effectively usable before the new return trip.
    #
    # Example:
    #
    # hotel 22 -> 23
    # departure 22 at 19:00
    #
    # usable nights = 0
    # unused nights = 1
    usable_nights = max(
        (
            min(
                departure_date,
                hotel.check_out,
            )
            - hotel.check_in
        ).days,
        0,
    )

    unused_nights = max(
        booked_nights
        - usable_nights,
        0,
    )

    if unused_nights <= 0:
        return None

    estimated_amount = (
        _estimate_unused_amount(
            hotel_price=hotel.price,
            booked_nights=booked_nights,
            unused_nights=unused_nights,
        )
    )

    nights_word = _nights_word(
        unused_nights
    )

    departure_label = (
        departure.strftime(
            "%d.%m в %H:%M"
        )
    )

    checkout_label = (
        hotel.check_out.strftime(
            "%d.%m"
        )
    )

    amount_text = ""

    if estimated_amount > 0:
        amount_text = (
            " Потенциально можно "
            "сэкономить около "
            f"{_money(estimated_amount)}."
        )

    return RescueInsight(
        type=(
            InsightType
            .HOTEL_UNUSED_NIGHTS
        ),
        severity=(
            InsightSeverity.WARNING
        ),
        title=(
            "Часть брони отеля "
            "может не понадобиться"
        ),
        description=(
            "Новый обратный маршрут "
            f"отправляется {departure_label}, "
            "а текущая бронь отеля "
            f"рассчитана до {checkout_label}. "
            f"{unused_nights} "
            f"{nights_word} "
            "может остаться неиспользованной."
            f"{amount_text}"
        ),
        component=(
            RescueComponent.HOTEL
        ),
        action=(
            InsightAction
            .SEARCH_SHORTER_HOTEL
        ),
        estimated_amount=(
            estimated_amount
        ),
        estimated_unused_nights=(
            unused_nights
        ),
    )


def _estimate_unused_amount(
    *,
    hotel_price: int,
    booked_nights: int,
    unused_nights: int,
) -> int:
    if (
        hotel_price <= 0
        or booked_nights <= 0
        or unused_nights <= 0
    ):
        return 0

    amount = (
        hotel_price
        * unused_nights
        / booked_nights
    )

    return int(
        round(
            amount
        )
    )


def _money(
    value: int,
) -> str:
    return (
        f"{value:,}"
        .replace(",", " ")
        + " ₽"
    )


def _nights_word(
    value: int,
) -> str:
    last_two = (
        value % 100
    )

    if (
        11
        <= last_two
        <= 14
    ):
        return "ночей"

    last = (
        value % 10
    )

    if last == 1:
        return "ночь"

    if (
        2
        <= last
        <= 4
    ):
        return "ночи"

    return "ночей"