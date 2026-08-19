from __future__ import annotations

from typing import Any, TypedDict


class RescueState(
    TypedDict,
    total=False,
):
    previous_trip: dict[
        str,
        Any,
    ]

    current_journey: dict[
        str,
        Any,
    ]

    request_text: str
    reference_date: str

    updated_trip: dict[
        str,
        Any,
    ]

    diff: dict[
        str,
        Any,
    ]

    validation: dict[
        str,
        Any,
    ]

    planning: dict[
        str,
        Any,
    ]

    execution: dict[
        str,
        Any,
    ]

    result: dict[
        str,
        Any,
    ]