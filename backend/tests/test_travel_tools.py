from datetime import date, time
from urllib.parse import parse_qs, urlsplit

import pytest

from app.schemas import AgentNextAction, TravelService, TripDetails
from app.travel_rules import next_travel_action, search_redirect_url, validate_trip


def test_tools_keep_incomplete_trip_in_collection_flow() -> None:
    trip = TripDetails(
        service_type=TravelService.BUS,
        origin="Москва",
        destination="Тула",
    )

    assert validate_trip(trip)["missing_fields"] == [
        "start_date",
        "passengers",
        "budget",
        "preferred_time",
    ]
    assert next_travel_action(trip) is AgentNextAction.COLLECT_TRIP_DETAILS
    with pytest.raises(ValueError, match="missing fields"):
        search_redirect_url(trip)


def test_tools_search_international_flight_before_documents() -> None:
    trip = TripDetails(
        service_type=TravelService.FLIGHT,
        origin="Москва",
        destination="Париж",
        start_date=date(2026, 9, 1),
        preferred_time=time(10, 30),
        passengers=1,
        budget=50_000,
        is_international=True,
    )

    assert next_travel_action(trip) is AgentNextAction.REDIRECT_TO_SEARCH


def test_search_redirect_is_built_from_normalized_trip() -> None:
    trip = TripDetails(
        service_type=TravelService.HOTEL,
        destination="Сочи",
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 7),
        passengers=2,
        budget=40_000,
    )

    redirect = urlsplit(search_redirect_url(trip))
    query = parse_qs(redirect.query)

    assert redirect.path == "/search/hotel"
    assert query == {
        "destination": ["Сочи"],
        "date": ["2026-09-01"],
        "return_date": ["2026-09-07"],
        "passengers": ["2"],
        "budget": ["40000"],
        "currency": ["RUB"],
    }
