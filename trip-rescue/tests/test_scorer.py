from app.models.rescue import (
    RescueComponent,
)
from app.rescue.scorer import (
    score_rescue_plan,
)


def test_hotel_is_cheapest_component_to_change() -> None:
    hotel = score_rescue_plan(
        replace_components=[
            RescueComponent.HOTEL
        ]
    )

    inbound = score_rescue_plan(
        replace_components=[
            RescueComponent.INBOUND
        ]
    )

    outbound = score_rescue_plan(
        replace_components=[
            RescueComponent.OUTBOUND
        ]
    )

    assert hotel < inbound
    assert inbound < outbound


def test_multiple_changes_have_extra_penalty() -> None:
    inbound = score_rescue_plan(
        replace_components=[
            RescueComponent.INBOUND
        ]
    )

    combination = (
        score_rescue_plan(
            replace_components=[
                RescueComponent.HOTEL,
                RescueComponent.INBOUND,
            ]
        )
    )

    assert combination > inbound


def test_empty_plan_has_zero_score() -> None:
    assert (
        score_rescue_plan(
            replace_components=[]
        )
        == 0.0
    )