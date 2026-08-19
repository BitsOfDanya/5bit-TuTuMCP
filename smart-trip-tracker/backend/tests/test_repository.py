from datetime import date
from pathlib import Path

from app.provider import DemoTripOfferProvider
from app.repository import SQLiteTrackingRepository
from app.schemas import TripIntent
from app.service import TripTrackingService


def test_sqlite_history_survives_service_restart(tmp_path: Path) -> None:
    database_path = tmp_path / "tracker.db"
    intent = TripIntent(
        origin="Москва",
        destination="Казань",
        departure_date=date(2026, 9, 10),
        return_date=date(2026, 9, 13),
        adults=1,
        budget=45_000,
        direct_only=True,
        hotel_rating_min=8,
    )

    first_service = TripTrackingService(
        DemoTripOfferProvider(),
        SQLiteTrackingRepository(database_path),
    )
    created = first_service.create(intent)
    refreshed = first_service.refresh(created.id, simulated=True)

    restarted_service = TripTrackingService(
        DemoTripOfferProvider(),
        SQLiteTrackingRepository(database_path),
    )
    restored = restarted_service.get(created.id)

    assert restored.id == created.id
    assert restored.intent == intent
    assert len(restored.history) == 2
    assert restored.summary.current_price == refreshed.summary.current_price
    assert restored.summary.minimum_price < created.summary.current_price
