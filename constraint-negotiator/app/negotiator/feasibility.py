from datetime import datetime

from app.models.journey import JourneyOption
from app.models.relaxation import ConstraintChange
from app.models.trip import ConstraintField, TripSpec


def _as_local_naive(value: datetime) -> datetime:
    """
    TripSpec stores local wall-clock constraints without timezone.

    Tutu returns offset-aware datetimes such as:
    2026-08-23T19:00:00+03:00

    For constraint comparison we compare the local wall-clock
    date/time from the Tutu response with the local TripSpec.
    """
    return value.replace(tzinfo=None)


def evaluate_constraints(
    trip: TripSpec,
    journey: JourneyOption,
) -> list[ConstraintChange]:

    violations: list[ConstraintChange] = []

    # ---------------------------------------------------------
    # Budget
    # ---------------------------------------------------------

    if (
        trip.budget is not None
        and journey.total_price > trip.budget
    ):
        delta = journey.total_price - trip.budget

        violations.append(
            ConstraintChange(
                field=ConstraintField.BUDGET,
                title=f"+{delta:,} ₽".replace(",", " "),
                description="Увеличить бюджет поездки",
                old_value=trip.budget,
                new_value=journey.total_price,
                magnitude=float(delta),
            )
        )

    # ---------------------------------------------------------
    # Outbound departure
    # ---------------------------------------------------------

    if trip.outbound_after is not None:
        required_departure = _as_local_naive(
            datetime.combine(
                trip.outbound_date,
                trip.outbound_after,
            )
        )

        actual_departure = _as_local_naive(
            journey.outbound.departure
        )

        if actual_departure < required_departure:
            delta_minutes = int(
                (
                    required_departure
                    - actual_departure
                ).total_seconds()
                // 60
            )

            violations.append(
                ConstraintChange(
                    field=ConstraintField.OUTBOUND_AFTER,
                    title=f"−{delta_minutes} мин",
                    description=(
                        "Выехать раньше — "
                        f"в {actual_departure.strftime('%H:%M')}"
                    ),
                    old_value=(
                        required_departure
                        .strftime("%Y-%m-%d %H:%M")
                    ),
                    new_value=(
                        actual_departure
                        .strftime("%Y-%m-%d %H:%M")
                    ),
                    magnitude=float(delta_minutes),
                )
            )

    # ---------------------------------------------------------
    # Return arrival
    # ---------------------------------------------------------

    if trip.return_before is not None:
        required_return = _as_local_naive(
            datetime.combine(
                trip.return_date,
                trip.return_before,
            )
        )

        actual_return = _as_local_naive(
            journey.inbound.arrival
        )

        if actual_return > required_return:
            delta_minutes = int(
                (
                    actual_return
                    - required_return
                ).total_seconds()
                // 60
            )

            violations.append(
                ConstraintChange(
                    field=ConstraintField.RETURN_BEFORE,
                    title=f"+{delta_minutes} мин",
                    description=(
                        "Вернуться позже — "
                        f"{actual_return.strftime('%d.%m в %H:%M')}"
                    ),
                    old_value=(
                        required_return
                        .strftime("%Y-%m-%d %H:%M")
                    ),
                    new_value=(
                        actual_return
                        .strftime("%Y-%m-%d %H:%M")
                    ),
                    magnitude=float(delta_minutes),
                )
            )

    # ---------------------------------------------------------
    # Transport exclusions
    # ---------------------------------------------------------

    excluded = set(
        trip.excluded_transport
    )

    used = journey.transport_modes

    violated_transport = (
        excluded.intersection(used)
    )

    if violated_transport:
        modes = ", ".join(
            sorted(
                mode.value
                for mode in violated_transport
            )
        )

        violations.append(
            ConstraintChange(
                field=ConstraintField.TRANSPORT,
                title="Разрешить другой транспорт",
                description=f"Разрешить: {modes}",
                old_value=[
                    mode.value
                    for mode
                    in trip.excluded_transport
                ],
                new_value=modes,
                magnitude=1.0,
            )
        )

    # ---------------------------------------------------------
    # Transfers
    # ---------------------------------------------------------

    if (
        trip.max_transfers is not None
        and journey.max_transfers
        > trip.max_transfers
    ):
        delta = (
            journey.max_transfers
            - trip.max_transfers
        )

        violations.append(
            ConstraintChange(
                field=ConstraintField.MAX_TRANSFERS,
                title=(
                    f"+{delta} "
                    f"{'пересадка' if delta == 1 else 'пересадки'}"
                ),
                description=(
                    "Разрешить больше пересадок"
                ),
                old_value=trip.max_transfers,
                new_value=journey.max_transfers,
                magnitude=float(delta),
            )
        )

    return violations
