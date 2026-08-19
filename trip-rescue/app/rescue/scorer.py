from __future__ import annotations

from app.models.rescue import RescueComponent


COMPONENT_CHANGE_COST: dict[
    RescueComponent,
    float,
] = {
    RescueComponent.HOTEL: 0.7,
    RescueComponent.INBOUND: 1.0,
    RescueComponent.OUTBOUND: 1.1,
}


def score_rescue_plan(
    *,
    replace_components: list[
        RescueComponent
    ],
) -> float:
    """
    Lower is better.

    We deliberately penalize changing multiple components,
    because Rescue should preserve as much of the accepted
    journey as possible.
    """

    if not replace_components:
        return 0.0

    score = sum(
        COMPONENT_CHANGE_COST[
            component
        ]
        for component
        in replace_components
    )

    if len(
        replace_components
    ) > 1:
        score += (
            0.35
            * (
                len(
                    replace_components
                )
                - 1
            )
        )

    return round(
        score,
        6,
    )