from datetime import date

from app.engine import select_best_trip
from app.provider import DemoTripOfferProvider
from app.schemas import RecommendationStatus, SimulationScenario, TripIntent
from app.service import TripTrackingService


def intent() -> TripIntent:
    return TripIntent(
        origin="Москва",
        destination="Казань",
        departure_date=date(2026, 9, 10),
        return_date=date(2026, 9, 13),
        adults=1,
        budget=45_000,
        direct_only=True,
        hotel_rating_min=8,
    )


def test_ranking_respects_constraints_and_builds_complete_trip() -> None:
    trip_intent = intent()
    candidates = DemoTripOfferProvider().search(trip_intent)

    best = select_best_trip(candidates, trip_intent)

    assert best.total_price <= trip_intent.budget
    assert best.transfers == 0
    assert best.hotel_rating >= 8
    assert 0 <= best.trip_score <= 100
    assert best.useful_time_hours > 0


def test_service_tracks_history_and_changes_recommendation() -> None:
    service = TripTrackingService(DemoTripOfferProvider())

    created = service.create(intent())
    dropped = service.simulate(created.id, SimulationScenario.DROP)
    spiked = service.simulate(created.id, SimulationScenario.SPIKE)

    assert created.recommendation.status is RecommendationStatus.COLLECTING_DATA
    assert len(spiked.history) == 3
    assert dropped.summary.current_price < created.summary.current_price
    assert dropped.recommendation.status is RecommendationStatus.BUY_NOW
    assert spiked.summary.current_price > dropped.summary.current_price
    assert spiked.summary.difference_from_min > 0
    assert spiked.recommendation.status is RecommendationStatus.WAIT
