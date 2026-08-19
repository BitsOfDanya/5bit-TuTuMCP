from __future__ import annotations

from itertools import combinations

from app.models.journey import JourneyOption
from app.models.rescue import (
    RescueComponent,
    RescuePlanningResult,
    RescuePlanReason,
    RescueSearchPlan,
    RescueValidation,
)
from app.models.trip import TripSpec
from app.rescue.policy import RescuePolicy
from app.rescue.scorer import score_rescue_plan


COMPONENT_ORDER: tuple[
    RescueComponent,
    ...,
] = (
    RescueComponent.OUTBOUND,
    RescueComponent.HOTEL,
    RescueComponent.INBOUND,
)


def build_rescue_search_plans(
    *,
    trip: TripSpec,
    journey: JourneyOption,
    validation: RescueValidation,
    policy: RescuePolicy | None = None,
) -> RescuePlanningResult:
    """
    Convert validation result into concrete search strategies.

    Examples:

    return deadline changed:
        preserve outbound
        preserve hotel
        search inbound

    budget reduced:
        try hotel only
        try inbound only
        try outbound only
        then minimal two-component combinations
    """

    active_policy = (
        policy
        or RescuePolicy()
    )

    if validation.journey_valid:
        return RescuePlanningResult(
            status="no_change",
            plans=[],
        )

    mandatory = _ordered_components(
        validation.replace_components
    )

    candidate_sets: list[
        tuple[
            RescueComponent,
            ...,
        ]
    ] = []

    # ---------------------------------------------------------
    # Constraint violation only
    # ---------------------------------------------------------

    if not validation.budget_violation:
        if mandatory:
            candidate_sets.append(
                tuple(
                    mandatory
                )
            )

    # ---------------------------------------------------------
    # Budget optimization
    # ---------------------------------------------------------

    else:
        budget_components = (
            active_policy
            .budget_components(
                journey=journey
            )
        )

        if mandatory:
            # First try replacing only what is already
            # physically invalid.
            #
            # The new variant may also happen to be cheaper.
            candidate_sets.append(
                tuple(
                    mandatory
                )
            )

            # Then allow one or more additional components,
            # while respecting the budget-rebuild policy.
            remaining = [
                component
                for component
                in budget_components
                if component
                not in mandatory
            ]

            max_total = max(
                len(mandatory),
                active_policy
                .max_budget_replacement_components,
            )

            extra_capacity = (
                max_total
                - len(mandatory)
            )

            for extra_count in range(
                1,
                extra_capacity + 1,
            ):
                for extra in combinations(
                    remaining,
                    extra_count,
                ):
                    candidate_sets.append(
                        tuple(
                            mandatory
                        )
                        + extra
                    )

        else:
            # Pure budget problem.
            #
            # Start with the least disruptive single-component
            # rebuilds and then allow small combinations.
            max_count = min(
                active_policy
                .max_budget_replacement_components,
                len(
                    budget_components
                ),
            )

            for count in range(
                1,
                max_count + 1,
            ):
                for candidate in combinations(
                    budget_components,
                    count,
                ):
                    candidate_sets.append(
                        candidate
                    )

    candidate_sets = (
        _deduplicate_candidate_sets(
            candidate_sets
        )
    )

    plans: list[
        RescueSearchPlan
    ] = []

    for candidate in candidate_sets:
        replace_components = (
            _ordered_components(
                candidate
            )
        )

        preserve_components = (
            _preserved_components(
                journey=journey,
                replace_components=(
                    replace_components
                ),
            )
        )

        reason = _plan_reason(
            mandatory=mandatory,
            budget_violation=(
                validation.budget_violation
            ),
        )

        score = score_rescue_plan(
            replace_components=(
                replace_components
            )
        )

        plan = RescueSearchPlan(
            id=_build_plan_id(
                replace_components
            ),
            reason=reason,
            replace_components=(
                replace_components
            ),
            preserve_components=(
                preserve_components
            ),
            mandatory_components=(
                mandatory
            ),
            budget_target_saving=(
                validation
                .budget_exceeded_by
            ),
            score=score,
            description=(
                _build_description(
                    replace_components=(
                        replace_components
                    ),
                    preserve_components=(
                        preserve_components
                    ),
                    budget_target_saving=(
                        validation
                        .budget_exceeded_by
                    ),
                )
            ),
        )

        plans.append(
            plan
        )

    plans.sort(
        key=lambda plan: (
            plan.score,
            len(
                plan.replace_components
            ),
            plan.id,
        )
    )

    plans = plans[
        :active_policy.max_plans
    ]

    return RescuePlanningResult(
        status=(
            "search_required"
            if plans
            else "no_change"
        ),
        plans=plans,
    )


def _available_components(
    *,
    journey: JourneyOption,
) -> list[RescueComponent]:

    result = [
        RescueComponent.OUTBOUND,
    ]

    if journey.hotel is not None:
        result.append(
            RescueComponent.HOTEL
        )

    result.append(
        RescueComponent.INBOUND
    )

    return result


def _preserved_components(
    *,
    journey: JourneyOption,
    replace_components: list[
        RescueComponent
    ],
) -> list[RescueComponent]:

    replacing = set(
        replace_components
    )

    return [
        component
        for component
        in _available_components(
            journey=journey
        )
        if component
        not in replacing
    ]


def _ordered_components(
    components,
) -> list[RescueComponent]:

    values = set(
        components
    )

    return [
        component
        for component
        in COMPONENT_ORDER
        if component in values
    ]


def _deduplicate_candidate_sets(
    candidates: list[
        tuple[
            RescueComponent,
            ...,
        ]
    ],
) -> list[
    tuple[
        RescueComponent,
        ...,
    ]
]:

    seen: set[
        tuple[str, ...]
    ] = set()

    result: list[
        tuple[
            RescueComponent,
            ...,
        ]
    ] = []

    for candidate in candidates:
        ordered = (
            _ordered_components(
                candidate
            )
        )

        signature = tuple(
            component.value
            for component
            in ordered
        )

        if signature in seen:
            continue

        seen.add(
            signature
        )

        result.append(
            tuple(
                ordered
            )
        )

    return result


def _plan_reason(
    *,
    mandatory: list[
        RescueComponent
    ],
    budget_violation: bool,
) -> RescuePlanReason:

    if (
        mandatory
        and budget_violation
    ):
        return (
            RescuePlanReason.MIXED
        )

    if budget_violation:
        return (
            RescuePlanReason
            .BUDGET_OPTIMIZATION
        )

    return (
        RescuePlanReason
        .CONSTRAINT_VIOLATION
    )


def _build_plan_id(
    replace_components: list[
        RescueComponent
    ],
) -> str:

    suffix = "-".join(
        component.value
        for component
        in replace_components
    )

    return (
        f"rescue-search-{suffix}"
    )


def _build_description(
    *,
    replace_components: list[
        RescueComponent
    ],
    preserve_components: list[
        RescueComponent
    ],
    budget_target_saving: int,
) -> str:

    replace_text = ", ".join(
        _component_label(
            component
        )
        for component
        in replace_components
    )

    if preserve_components:
        preserve_text = ", ".join(
            _component_label(
                component
            )
            for component
            in preserve_components
        )
    else:
        preserve_text = "ничего"

    result = (
        f"Заменить: {replace_text}. "
        f"Сохранить: {preserve_text}."
    )

    if budget_target_saving > 0:
        result += (
            " Требуемая экономия: "
            f"{budget_target_saving} ₽."
        )

    return result


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