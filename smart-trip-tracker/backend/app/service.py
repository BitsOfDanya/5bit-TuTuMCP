from datetime import UTC, datetime, timedelta
from threading import Lock
from uuid import UUID, uuid4

from app.engine import recommend, select_best_trip, summarize_prices
from app.negotiator import NegotiationResultInput, adapt_negotiation_result
from app.provider import TripOfferProvider
from app.repository import InMemoryTrackingRepository, TrackingRepository, TrackingState
from app.schemas import (
    BestTrip,
    PricePoint,
    SimulationScenario,
    TrackingListResponse,
    TripIntent,
    TripSnapshot,
    TripTrackingResponse,
)

SIMULATION_FACTORS = {
    SimulationScenario.DROP: 0.93,
    SimulationScenario.SPIKE: 1.20,
}


class InactiveTrackingError(RuntimeError):
    pass

class TrackingRouteMismatchError(ValueError):
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

    def create_from_negotiation(
        self,
        result: NegotiationResultInput,
    ) -> TripTrackingResponse:
        now = datetime.now(UTC)
        intent, best_trip = adapt_negotiation_result(result)
        state = self.repository.create(intent, now)
        state = self._store_snapshot(
            state,
            best_trip=best_trip,
            simulated=False,
            timestamp=now,
        )
        return self._response(state)

    def record_negotiation(
        self,
        tracking_id: UUID,
        result: NegotiationResultInput,
    ) -> TripTrackingResponse:
        lock = self._tracking_lock(tracking_id)
        with lock:
            state = self.repository.get(tracking_id)
            self._ensure_active(state)
            intent, best_trip = adapt_negotiation_result(result)
            if (
                intent.origin.casefold() != state.intent.origin.casefold()
                or intent.destination.casefold() != state.intent.destination.casefold()
                or intent.departure_date != state.intent.departure_date
                or intent.return_date != state.intent.return_date
            ):
                raise TrackingRouteMismatchError(
                    "Negotiation result belongs to a different trip."
                )
            previous_time = state.snapshots[-1].timestamp
            timestamp = max(datetime.now(UTC), previous_time + timedelta(seconds=1))
            state = self._store_snapshot(
                state,
                best_trip=best_trip,
                simulated=False,
                timestamp=timestamp,
            )
            return self._response(state)

    def get(self, tracking_id: UUID) -> TripTrackingResponse:
        return self._response(self.repository.get(tracking_id))

    def list(self) -> TrackingListResponse:
        return TrackingListResponse(
            items=[self._response(state) for state in self.repository.list()]
        )

    def refresh(self, tracking_id: UUID) -> TripTrackingResponse:
        lock = self._tracking_lock(tracking_id)
        with lock:
            state = self.repository.get(tracking_id)
            self._ensure_active(state)
            previous_time = state.snapshots[-1].timestamp
            timestamp = max(datetime.now(UTC), previous_time + timedelta(seconds=1))
            best_trip = select_best_trip(self.provider.search(state.intent), state.intent)
            state = self._store_snapshot(
                state,
                best_trip=best_trip,
                simulated=False,
                timestamp=timestamp,
            )
            return self._response(state)

    def simulate(
        self,
        tracking_id: UUID,
        scenario: SimulationScenario,
    ) -> TripTrackingResponse:
        lock = self._tracking_lock(tracking_id)
        with lock:
            state = self.repository.get(tracking_id)
            self._ensure_active(state)
            latest = state.snapshots[-1]
            factor = SIMULATION_FACTORS[scenario]
            transport_price = round(latest.best_trip.transport_price * factor)
            hotel_price = round(latest.best_trip.hotel_price * factor)
            best_trip = latest.best_trip.model_copy(
                update={
                    "transport_price": transport_price,
                    "hotel_price": hotel_price,
                    "total_price": transport_price + hotel_price,
                    "transport": latest.best_trip.transport.model_copy(
                        update={"price": transport_price}
                    ),
                    "hotel": (
                        latest.best_trip.hotel.model_copy(
                            update={"price_total": hotel_price}
                        )
                        if latest.best_trip.hotel is not None
                        else None
                    ),
                }
            )
            state = self._store_snapshot(
                state,
                best_trip=best_trip,
                simulated=True,
                timestamp=latest.timestamp + timedelta(hours=6),
            )
            return self._response(state)

    def stop(self, tracking_id: UUID) -> TripTrackingResponse:
        return self._response(self.repository.stop(tracking_id))

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

    @staticmethod
    def _ensure_active(state: TrackingState) -> None:
        if not state.active:
            raise InactiveTrackingError("Trip tracking is stopped.")
