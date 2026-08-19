from app.models.journey import JourneyOption
from app.models.relaxation import ConstraintChange
from app.models.trip import ConstraintField, TripSpec


def evaluate_constraints(
    trip: TripSpec,
    journey: JourneyOption,
) -> list[ConstraintChange]:

    violations: list[ConstraintChange] = []

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

    if trip.outbound_after is not None:
        required = trip.outbound_after
        actual = journey.outbound.departure.time()

        required_minutes = required.hour * 60 + required.minute
        actual_minutes = actual.hour * 60 + actual.minute

        if actual_minutes < required_minutes:
            delta = required_minutes - actual_minutes

            violations.append(
                ConstraintChange(
                    field=ConstraintField.OUTBOUND_AFTER,
                    title=f"−{delta} мин",
                    description=(
                        f"Выехать раньше — "
                        f"в {actual.strftime('%H:%M')}"
                    ),
                    old_value=required.strftime("%H:%M"),
                    new_value=actual.strftime("%H:%M"),
                    magnitude=float(delta),
                )
            )

    if trip.return_before is not None:
        required = trip.return_before
        actual = journey.inbound.arrival.time()

        required_minutes = required.hour * 60 + required.minute
        actual_minutes = actual.hour * 60 + actual.minute

        if actual_minutes > required_minutes:
            delta = actual_minutes - required_minutes

            violations.append(
                ConstraintChange(
                    field=ConstraintField.RETURN_BEFORE,
                    title=f"+{delta} мин",
                    description=(
                        f"Вернуться позже — "
                        f"в {actual.strftime('%H:%M')}"
                    ),
                    old_value=required.strftime("%H:%M"),
                    new_value=actual.strftime("%H:%M"),
                    magnitude=float(delta),
                )
            )

    excluded = set(trip.excluded_transport)
    used = journey.transport_modes

    violated_transport = excluded.intersection(used)

    if violated_transport:
        modes = ", ".join(
            sorted(mode.value for mode in violated_transport)
        )

        violations.append(
            ConstraintChange(
                field=ConstraintField.TRANSPORT,
                title="Разрешить другой транспорт",
                description=f"Разрешить: {modes}",
                old_value=[
                    mode.value
                    for mode in trip.excluded_transport
                ],
                new_value=modes,
                magnitude=1.0,
            )
        )

    if (
        trip.max_transfers is not None
        and journey.max_transfers > trip.max_transfers
    ):
        delta = journey.max_transfers - trip.max_transfers

        violations.append(
            ConstraintChange(
                field=ConstraintField.MAX_TRANSFERS,
                title=f"+{delta} пересадка",
                description="Разрешить больше пересадок",
                old_value=trip.max_transfers,
                new_value=journey.max_transfers,
                magnitude=float(delta),
            )
        )

    return violations