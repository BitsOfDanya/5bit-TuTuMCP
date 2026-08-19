from __future__ import annotations

import pytest

from app.preferences.cold_start import (
    ColdStartChoice,
    ColdStartDimension,
    evaluate_cold_start,
    get_cold_start_questions,
)


def test_default_deck_has_six_questions() -> None:
    questions = (
        get_cold_start_questions()
    )

    assert len(questions) == 6

    assert len(
        {
            question.id
            for question
            in questions
        }
    ) == 6


def test_four_choices_are_enough_for_completion() -> None:
    questions = (
        get_cold_start_questions()
    )

    choices = [
        ColdStartChoice(
            question_id=question.id,
            selected_option_id=(
                question.left.id
            ),
        )
        for question
        in questions[:4]
    ]

    result = evaluate_cold_start(
        choices=choices
    )

    assert (
        result.questions_answered
        == 4
    )

    assert (
        result.completed
        is True
    )

    assert (
        result.confidence
        > 0.6
    )


def test_three_choices_are_partial() -> None:
    questions = (
        get_cold_start_questions()
    )

    choices = [
        ColdStartChoice(
            question_id=question.id,
            selected_option_id=(
                question.left.id
            ),
        )
        for question
        in questions[:3]
    ]

    result = evaluate_cold_start(
        choices=choices
    )

    assert (
        result.questions_answered
        == 3
    )

    assert (
        result.completed
        is False
    )


def test_cheap_choices_raise_price_sensitivity() -> None:
    questions = (
        get_cold_start_questions()
    )

    choices = [
        ColdStartChoice(
            question_id=(
                "price-vs-speed"
            ),
            selected_option_id=(
                "price-vs-speed:cheap"
            ),
        ),
        ColdStartChoice(
            question_id=(
                "direct-vs-cheaper"
            ),
            selected_option_id=(
                "direct-vs-cheaper:"
                "transfer"
            ),
        ),
        ColdStartChoice(
            question_id=(
                "hotel-quality-vs-price"
            ),
            selected_option_id=(
                "hotel-quality-vs-price:"
                "budget"
            ),
        ),
        ColdStartChoice(
            question_id=(
                "arrival-time-vs-price"
            ),
            selected_option_id=(
                "arrival-time-vs-price:"
                "cheaper"
            ),
        ),
    ]

    result = evaluate_cold_start(
        choices=choices,
        questions=questions,
    )

    assert result.completed

    assert (
        result.weights.price
        > result.weights.duration
    )

    assert (
        result.weights.price
        > result.weights.hotel_quality
    )


def test_fast_choices_raise_duration_sensitivity() -> None:
    choices = [
        ColdStartChoice(
            question_id=(
                "price-vs-speed"
            ),
            selected_option_id=(
                "price-vs-speed:fast"
            ),
        ),
        ColdStartChoice(
            question_id=(
                "direct-vs-cheaper"
            ),
            selected_option_id=(
                "direct-vs-cheaper:"
                "direct"
            ),
        ),
        ColdStartChoice(
            question_id=(
                "arrival-time-vs-price"
            ),
            selected_option_id=(
                "arrival-time-vs-price:"
                "earlier"
            ),
        ),
        ColdStartChoice(
            question_id=(
                "flight-direct-vs-connection"
            ),
            selected_option_id=(
                "flight-direct-vs-connection:"
                "direct"
            ),
        ),
    ]

    result = evaluate_cold_start(
        choices=choices
    )

    assert result.completed

    assert (
        result.weights.duration
        > result.weights.price
    )


def test_direct_choices_raise_transfer_sensitivity() -> None:
    choices = [
        ColdStartChoice(
            question_id=(
                "direct-vs-cheaper"
            ),
            selected_option_id=(
                "direct-vs-cheaper:"
                "direct"
            ),
        ),
        ColdStartChoice(
            question_id=(
                "flight-direct-vs-connection"
            ),
            selected_option_id=(
                "flight-direct-vs-connection:"
                "direct"
            ),
        ),
        ColdStartChoice(
            question_id=(
                "train-vs-flight"
            ),
            selected_option_id=(
                "train-vs-flight:train"
            ),
        ),
        ColdStartChoice(
            question_id=(
                "arrival-time-vs-price"
            ),
            selected_option_id=(
                "arrival-time-vs-price:"
                "earlier"
            ),
        ),
    ]

    result = evaluate_cold_start(
        choices=choices
    )

    assert (
        result.weights.transfers
        > 0.35
    )


def test_comfort_choice_raises_hotel_quality() -> None:
    questions = (
        get_cold_start_questions()
    )

    choices = [
        ColdStartChoice(
            question_id=(
                "hotel-quality-vs-price"
            ),
            selected_option_id=(
                "hotel-quality-vs-price:"
                "comfort"
            ),
        ),
        ColdStartChoice(
            question_id=(
                "train-vs-flight"
            ),
            selected_option_id=(
                "train-vs-flight:train"
            ),
        ),
        ColdStartChoice(
            question_id=(
                "direct-vs-cheaper"
            ),
            selected_option_id=(
                "direct-vs-cheaper:"
                "direct"
            ),
        ),
        ColdStartChoice(
            question_id=(
                "arrival-time-vs-price"
            ),
            selected_option_id=(
                "arrival-time-vs-price:"
                "earlier"
            ),
        ),
    ]

    result = evaluate_cold_start(
        choices=choices,
        questions=questions,
    )

    assert (
        result.weights.hotel_quality
        > 0.35
    )


def test_transport_choice_builds_affinity() -> None:
    choices = [
        ColdStartChoice(
            question_id=(
                "train-vs-flight"
            ),
            selected_option_id=(
                "train-vs-flight:train"
            ),
        )
    ]

    result = evaluate_cold_start(
        choices=choices
    )

    assert (
        result.transport_affinity[
            "train"
        ]
        > 0
    )

    assert (
        result.transport_affinity[
            "flight"
        ]
        < 0
    )


def test_unknown_question_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="Unknown Cold Start",
    ):
        evaluate_cold_start(
            choices=[
                ColdStartChoice(
                    question_id="missing",
                    selected_option_id=(
                        "whatever"
                    ),
                )
            ]
        )


def test_foreign_option_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "does not belong"
        ),
    ):
        evaluate_cold_start(
            choices=[
                ColdStartChoice(
                    question_id=(
                        "train-vs-flight"
                    ),
                    selected_option_id=(
                        "price-vs-speed:cheap"
                    ),
                )
            ]
        )


def test_duplicate_question_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="Duplicate Cold Start",
    ):
        evaluate_cold_start(
            choices=[
                ColdStartChoice(
                    question_id=(
                        "train-vs-flight"
                    ),
                    selected_option_id=(
                        "train-vs-flight:train"
                    ),
                ),
                ColdStartChoice(
                    question_id=(
                        "train-vs-flight"
                    ),
                    selected_option_id=(
                        "train-vs-flight:flight"
                    ),
                ),
            ]
        )


def test_signals_explain_result() -> None:
    result = evaluate_cold_start(
        choices=[
            ColdStartChoice(
                question_id=(
                    "price-vs-speed"
                ),
                selected_option_id=(
                    "price-vs-speed:cheap"
                ),
            )
        ]
    )

    dimensions = {
        signal.dimension
        for signal
        in result.signals
    }

    assert (
        ColdStartDimension.PRICE
        in dimensions
    )

    assert (
        ColdStartDimension.DURATION
        in dimensions
    )

    assert (
        ColdStartDimension.TRANSPORT
        in dimensions
    )