from __future__ import annotations

from datetime import datetime

from app.models.journey import (
    JourneyOption,
    TransportSegment,
)
from app.models.rescue import (
    ComponentAction,
    ComponentValidation,
    RescueComponent,
    RescueValidation,
    TripDiff,
    TripField,
    ValidationReason,
)
from app.models.trip import (
    TransportMode,
    TripSpec,
)


STRUCTURAL_REPLACEMENT_FIELDS: dict[
    TripField,
    tuple[RescueComponent, ...],
] = {
    TripField.ORIGIN: (
        RescueComponent.OUTBOUND,
        RescueComponent.INBOUND,
    ),

    TripField.DESTINATION: (
        RescueComponent.OUTBOUND,
        RescueComponent.HOTEL,
        RescueComponent.INBOUND,
    ),

    TripField.OUTBOUND_DATE: (
        RescueComponent.OUTBOUND,
        RescueComponent.HOTEL,
    ),

    TripField.RETURN_DATE: (
        RescueComponent.HOTEL,
        RescueComponent.INBOUND,
    ),

    TripField.TRAVELERS: (
        RescueComponent.OUTBOUND,
        RescueComponent.HOTEL,
        RescueComponent.INBOUND,
    ),
}


COMPONENT_ORDER: tuple[
    RescueComponent,
    ...,
] = (
    RescueComponent.OUTBOUND,
    RescueComponent.HOTEL,
    RescueComponent.INBOUND,
)


def validate_current_journey(
    *,
    trip: TripSpec,
    journey: JourneyOption,
    diff: TripDiff,
) -> RescueValidation:

    validations: dict[
        RescueComponent,
        ComponentValidation,
    ] = {
        component: ComponentValidation(
            component=component,
            action=ComponentAction.PRESERVE,
            valid=True,
            reasons=[],
        )
        for component
        in COMPONENT_ORDER
    }

    # ---------------------------------------------------------
    # 1. Structural changes
    # ---------------------------------------------------------

    for change in diff.changes:
        components = (
            STRUCTURAL_REPLACEMENT_FIELDS
            .get(
                change.field,
                (),
            )
        )

        for component in components:
            _replace(
                validations=validations,
                component=component,
                reason=ValidationReason(
                    code=(
                        "structural_change"
                    ),
                    field=change.field,
                    message=(
                        "Изменение поля "
                        f"{change.field.value} "
                        "требует пересобрать "
                        f"{component.value}."
                    ),
                ),
            )

    # ---------------------------------------------------------
    # 2. Outbound time
    # ---------------------------------------------------------

    if (
        TripField.OUTBOUND_AFTER
        in diff.changed_fields
        and trip.outbound_after
        is not None
    ):
        required = (
            datetime.combine(
                trip.outbound_date,
                trip.outbound_after,
            )
        )

        actual = _as_local_naive(
            journey.outbound.departure
        )

        if actual < required:
            _replace(
                validations=validations,
                component=(
                    RescueComponent.OUTBOUND
                ),
                reason=ValidationReason(
                    code=(
                        "outbound_too_early"
                    ),
                    field=(
                        TripField.OUTBOUND_AFTER
                    ),
                    message=(
                        "Текущий маршрут туда "
                        f"отправляется "
                        f"{actual:%d.%m %H:%M}, "
                        "а теперь требуется "
                        f"не раньше "
                        f"{required:%d.%m %H:%M}."
                    ),
                ),
            )

    # ---------------------------------------------------------
    # 3. Return deadline
    # ---------------------------------------------------------

    if (
        TripField.RETURN_BEFORE
        in diff.changed_fields
        and trip.return_before
        is not None
    ):
        required = (
            datetime.combine(
                trip.return_date,
                trip.return_before,
            )
        )

        actual = _as_local_naive(
            journey.inbound.arrival
        )

        if actual > required:
            difference_minutes = int(
                (
                    actual
                    - required
                ).total_seconds()
                // 60
            )

            _replace(
                validations=validations,
                component=(
                    RescueComponent.INBOUND
                ),
                reason=ValidationReason(
                    code=(
                        "return_too_late"
                    ),
                    field=(
                        TripField.RETURN_BEFORE
                    ),
                    message=(
                        "Текущий обратный маршрут "
                        f"прибывает "
                        f"{actual:%d.%m %H:%M}, "
                        "а теперь требуется "
                        f"не позже "
                        f"{required:%d.%m %H:%M}. "
                        "Опоздание относительно "
                        "нового ограничения: "
                        f"{difference_minutes} мин."
                    ),
                ),
            )

    # ---------------------------------------------------------
    # 4. Excluded transport
    # ---------------------------------------------------------

    if (
        TripField.EXCLUDED_TRANSPORT
        in diff.changed_fields
    ):
        excluded = set(
            trip.excluded_transport
        )

        _validate_transport_exclusion(
            segment=journey.outbound,
            component=(
                RescueComponent.OUTBOUND
            ),
            excluded=excluded,
            validations=validations,
        )

        _validate_transport_exclusion(
            segment=journey.inbound,
            component=(
                RescueComponent.INBOUND
            ),
            excluded=excluded,
            validations=validations,
        )

    # ---------------------------------------------------------
    # 5. Transfers
    # ---------------------------------------------------------

    if (
        TripField.MAX_TRANSFERS
        in diff.changed_fields
        and trip.max_transfers
        is not None
    ):
        _validate_transfers(
            segment=journey.outbound,
            component=(
                RescueComponent.OUTBOUND
            ),
            max_transfers=(
                trip.max_transfers
            ),
            validations=validations,
        )

        _validate_transfers(
            segment=journey.inbound,
            component=(
                RescueComponent.INBOUND
            ),
            max_transfers=(
                trip.max_transfers
            ),
            validations=validations,
        )

    # ---------------------------------------------------------
    # 6. Preferred transport
    #
    # This is deliberately NOT a replacement condition.
    #
    # Preferred transport is a preference, not a physical
    # invalidation of the current journey.
    # Planner/scorer may later use it to rank alternatives.
    # ---------------------------------------------------------

    # ---------------------------------------------------------
    # 7. Budget
    #
    # Budget is a global constraint.
    #
    # If current journey costs too much, we do NOT mark every
    # component as physically invalid. Planner will decide
    # which component(s) should be replaced to achieve the
    # required saving with minimum disruption.
    # ---------------------------------------------------------

    budget_violation = False
    budget_exceeded_by = 0

    global_reasons: list[
        ValidationReason
    ] = []

    if (
        trip.budget is not None
        and journey.total_price
        > trip.budget
    ):
        budget_violation = True

        budget_exceeded_by = (
            journey.total_price
            - trip.budget
        )

        global_reasons.append(
            ValidationReason(
                code="budget_exceeded",
                field=TripField.BUDGET,
                message=(
                    "Текущая поездка стоит "
                    f"{journey.total_price} ₽, "
                    "новый бюджет — "
                    f"{trip.budget} ₽. "
                    "Необходимо сэкономить "
                    f"{budget_exceeded_by} ₽."
                ),
            )
        )

    # ---------------------------------------------------------
    # Result
    # ---------------------------------------------------------

    ordered_components = [
        validations[component]
        for component
        in COMPONENT_ORDER
    ]

    preserved_components = [
        validation.component
        for validation
        in ordered_components
        if (
            validation.action
            == ComponentAction.PRESERVE
        )
    ]

    replace_components = [
        validation.component
        for validation
        in ordered_components
        if (
            validation.action
            == ComponentAction.REPLACE
        )
    ]

    journey_valid = (
        not replace_components
        and not budget_violation
    )

    return RescueValidation(
        journey_valid=journey_valid,
        components=ordered_components,
        preserved_components=(
            preserved_components
        ),
        replace_components=(
            replace_components
        ),
        budget_violation=(
            budget_violation
        ),
        budget_exceeded_by=(
            budget_exceeded_by
        ),
        global_reasons=(
            global_reasons
        ),
    )


def _validate_transport_exclusion(
    *,
    segment: TransportSegment,
    component: RescueComponent,
    excluded: set[TransportMode],
    validations: dict[
        RescueComponent,
        ComponentValidation,
    ],
) -> None:

    if segment.mode not in excluded:
        return

    _replace(
        validations=validations,
        component=component,
        reason=ValidationReason(
            code=(
                "transport_excluded"
            ),
            field=(
                TripField.EXCLUDED_TRANSPORT
            ),
            message=(
                "Текущий сегмент использует "
                f"{segment.mode.value}, "
                "который теперь исключён."
            ),
        ),
    )


def _validate_transfers(
    *,
    segment: TransportSegment,
    component: RescueComponent,
    max_transfers: int,
    validations: dict[
        RescueComponent,
        ComponentValidation,
    ],
) -> None:

    if (
        segment.transfers
        <= max_transfers
    ):
        return

    _replace(
        validations=validations,
        component=component,
        reason=ValidationReason(
            code=(
                "too_many_transfers"
            ),
            field=(
                TripField.MAX_TRANSFERS
            ),
            message=(
                "В текущем сегменте "
                f"{segment.transfers} пересадок, "
                "а теперь разрешено максимум "
                f"{max_transfers}."
            ),
        ),
    )


def _replace(
    *,
    validations: dict[
        RescueComponent,
        ComponentValidation,
    ],
    component: RescueComponent,
    reason: ValidationReason,
) -> None:

    current = validations[
        component
    ]

    current.action = (
        ComponentAction.REPLACE
    )

    current.valid = False

    if not any(
        existing.code
        == reason.code
        and existing.field
        == reason.field
        for existing
        in current.reasons
    ):
        current.reasons.append(
            reason
        )


def _as_local_naive(
    value: datetime,
) -> datetime:
    """
    MVP semantics are the same as in Constraint Negotiator:
    compare local wall-clock time supplied by Tutu.

    This intentionally keeps the calendar date while removing
    the timezone information.
    """

    return value.replace(
        tzinfo=None
    )