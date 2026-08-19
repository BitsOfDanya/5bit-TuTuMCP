from typing import TypedDict


class NegotiatorState(TypedDict, total=False):
    request_text: str
    reference_date: str

    trip_spec: dict

    candidate_journeys: list[dict]

    result: dict