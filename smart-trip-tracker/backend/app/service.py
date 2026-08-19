from datetime import UTC, datetime, timedelta
from threading import Lock
from uuid import UUID, uuid4

from app.engine import recommend, select_best_trip, summarize_prices
from app.provider import TripOfferProvider
from app.repository import InMemoryTrackingRepository, TrackingRepository, TrackingState
from app.schemas import (
    BestTrip,
    PricePoint,
    TrackingListResponse,
    TripIntent,
    TripSnapshot,
    TripTrackingResponse,
)

SIMULATION_FACTORS = (0.97, 0.93, 1.01, 0.96)


class InactiveTrackingError(RuntimeError):
    pass


class TripTrackingService:
    def __init__(
        self,
        provider: TripOfferProvider,
        repository: TrackingRepository | None = None,
    ) -> None:
        self.provider = provider
        self.repository = repository or InMemoryTrackingRepository()
        self._refresh_locks: dict[UUID, Lock] = {}
        self._locks_guard = Lock()

    def create(self, intent: TripIntent) -> TripTrackingResponse:
        now = datetime.now(UTC)
        best_trip = select_best_trip(self.provider.search(intent), intent)
        state = self.repository.create(intent, now)
        state = self._store_snapshot(
            state,
            best_trip=best_trip,
            simulated=False,
            timestamp=now,
        )
        return self._response(state)

    def get(self, tracking_id: UUID) -> TripTrackingResponse:
        return self._response(self.repository.get(tracking_id))

    def list(self) -> TrackingListResponse:
        return TrackingListResponse(
            items=[self._response(state) for state in self.repository.list()]
        )

    def refresh(self, tracking_id: UUID, *, simulated: bool = False) -> TripTrackingResponse:
        lock = self._tracking_lock(tracking_id)
        with lock:
            state = self.repository.get(tracking_id)
            if not state.active:
                raise InactiveTrackingError("Trip tracking is stopped.")
            previous_time = state.snapshots[-1].timestamp
            timestamp = previous_time + timedelta(hours=6) if simulated else datetime.now(UTC)
            state = self._add_snapshot(state, simulated=simulated, timestamp=timestamp)
            return self._response(state)

    def stop(self, tracking_id: UUID) -> TripTrackingResponse:
        return self._response(self.repository.stop(tracking_id))

    def _add_snapshot(
        self,
        state: TrackingState,
        *,
        simulated: bool,
        timestamp: datetime,
    ) -> TrackingState:
        best_trip = select_best_trip(self.provider.search(state.intent), state.intent)
        if simulated:
            factor = SIMULATION_FACTORS[(len(state.snapshots) - 1) % len(SIMULATION_FACTORS)]
            transport_price = round(best_trip.transport_price * factor)
            hotel_price = round(best_trip.hotel_price * factor)
            best_trip = best_trip.model_copy(
                update={
                    "transport_price": transport_price,
                    "hotel_price": hotel_price,
                    "total_price": transport_price + hotel_price,
                }
            )

        return self._store_snapshot(
            state,
            best_trip=best_trip,
            simulated=simulated,
            timestamp=timestamp,
        )

    def _store_snapshot(
        self,
        state: TrackingState,
        *,
        best_trip: BestTrip,
        simulated: bool,
        timestamp: datetime,
    ) -> TrackingState:
        return self.repository.add_snapshot(
            state.id,
            TripSnapshot(
                id=uuid4(),
                tracking_id=state.id,
                timestamp=timestamp,
                best_trip=best_trip,
                simulated=simulated,
            ),
        )

    def _response(self, state: TrackingState) -> TripTrackingResponse:
        snapshots = state.snapshots
        latest = snapshots[-1]
        return TripTrackingResponse(
            id=state.id,
            intent=state.intent,
            active=state.active,
            created_at=state.created_at,
            last_checked_at=latest.timestamp,
            summary=summarize_prices(snapshots),
            recommendation=recommend(snapshots),
            current_trip=latest.best_trip,
            history=[
                PricePoint(
                    timestamp=snapshot.timestamp,
                    total_price=snapshot.best_trip.total_price,
                    trip_score=snapshot.best_trip.trip_score,
                )
                for snapshot in snapshots
            ],
        )

    def _tracking_lock(self, tracking_id: UUID) -> Lock:
        with self._locks_guard:
            return self._refresh_locks.setdefault(tracking_id, Lock())
