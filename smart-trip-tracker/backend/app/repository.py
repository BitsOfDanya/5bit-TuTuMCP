from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Protocol
from uuid import UUID, uuid4

from app.schemas import BestTrip, TripIntent, TripSnapshot


class TrackingNotFoundError(LookupError):
    pass


@dataclass
class TrackingState:
    id: UUID
    intent: TripIntent
    active: bool
    created_at: datetime
    snapshots: list[TripSnapshot] = field(default_factory=list)


class TrackingRepository(Protocol):
    def create(self, intent: TripIntent, created_at: datetime) -> TrackingState: ...

    def get(self, tracking_id: UUID) -> TrackingState: ...

    def list(self) -> list[TrackingState]: ...

    def add_snapshot(self, tracking_id: UUID, snapshot: TripSnapshot) -> TrackingState: ...

    def stop(self, tracking_id: UUID) -> TrackingState: ...


class InMemoryTrackingRepository:
    """Stage-one storage. Replace this class with a database repository later."""

    def __init__(self) -> None:
        self._items: dict[UUID, TrackingState] = {}
        self._lock = RLock()

    def create(self, intent: TripIntent, created_at: datetime) -> TrackingState:
        with self._lock:
            state = TrackingState(
                id=uuid4(),
                intent=intent,
                active=True,
                created_at=created_at,
            )
            self._items[state.id] = state
            return state

    def get(self, tracking_id: UUID) -> TrackingState:
        with self._lock:
            state = self._items.get(tracking_id)
            if state is None:
                raise TrackingNotFoundError("Trip tracking was not found.")
            return state

    def list(self) -> list[TrackingState]:
        with self._lock:
            return sorted(self._items.values(), key=lambda item: item.created_at, reverse=True)

    def add_snapshot(self, tracking_id: UUID, snapshot: TripSnapshot) -> TrackingState:
        with self._lock:
            state = self.get(tracking_id)
            state.snapshots.append(snapshot)
            return state

    def stop(self, tracking_id: UUID) -> TrackingState:
        with self._lock:
            state = self.get(tracking_id)
            state.active = False
            return state


class SQLiteTrackingRepository:
    """Persistent stage-two repository using only the Python standard library."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def create(self, intent: TripIntent, created_at: datetime) -> TrackingState:
        state = TrackingState(
            id=uuid4(),
            intent=intent,
            active=True,
            created_at=created_at,
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO trip_trackings (id, intent, active, created_at)
                VALUES (?, ?, 1, ?)
                """,
                (str(state.id), intent.model_dump_json(), created_at.isoformat()),
            )
        return state

    def get(self, tracking_id: UUID) -> TrackingState:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, intent, active, created_at FROM trip_trackings WHERE id = ?",
                (str(tracking_id),),
            ).fetchone()
            if row is None:
                raise TrackingNotFoundError("Trip tracking was not found.")
            snapshots = connection.execute(
                """
                SELECT id, tracking_id, timestamp, best_trip, simulated
                FROM trip_snapshots
                WHERE tracking_id = ?
                ORDER BY timestamp, id
                """,
                (str(tracking_id),),
            ).fetchall()
        return self._state_from_rows(row, snapshots)

    def list(self) -> list[TrackingState]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, intent, active, created_at
                FROM trip_trackings
                ORDER BY created_at DESC
                """
            ).fetchall()
        return [self.get(UUID(row["id"])) for row in rows]

    def add_snapshot(self, tracking_id: UUID, snapshot: TripSnapshot) -> TrackingState:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO trip_snapshots
                    (id, tracking_id, timestamp, best_trip, simulated)
                SELECT ?, ?, ?, ?, ?
                WHERE EXISTS (SELECT 1 FROM trip_trackings WHERE id = ?)
                """,
                (
                    str(snapshot.id),
                    str(tracking_id),
                    snapshot.timestamp.isoformat(),
                    snapshot.best_trip.model_dump_json(),
                    int(snapshot.simulated),
                    str(tracking_id),
                ),
            )
            if cursor.rowcount != 1:
                raise TrackingNotFoundError("Trip tracking was not found.")
        return self.get(tracking_id)

    def stop(self, tracking_id: UUID) -> TrackingState:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE trip_trackings SET active = 0 WHERE id = ?",
                (str(tracking_id),),
            )
            if cursor.rowcount != 1:
                raise TrackingNotFoundError("Trip tracking was not found.")
        return self.get(tracking_id)

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS trip_trackings (
                    id TEXT PRIMARY KEY,
                    intent TEXT NOT NULL,
                    active INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS trip_snapshots (
                    id TEXT PRIMARY KEY,
                    tracking_id TEXT NOT NULL
                        REFERENCES trip_trackings(id) ON DELETE CASCADE,
                    timestamp TEXT NOT NULL,
                    best_trip TEXT NOT NULL,
                    simulated INTEGER NOT NULL DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS ix_trip_snapshots_tracking_time
                    ON trip_snapshots(tracking_id, timestamp);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    @staticmethod
    def _state_from_rows(
        row: sqlite3.Row,
        snapshot_rows: list[sqlite3.Row],
    ) -> TrackingState:
        tracking_id = UUID(row["id"])
        return TrackingState(
            id=tracking_id,
            intent=TripIntent.model_validate_json(row["intent"]),
            active=bool(row["active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            snapshots=[
                TripSnapshot(
                    id=UUID(snapshot["id"]),
                    tracking_id=tracking_id,
                    timestamp=datetime.fromisoformat(snapshot["timestamp"]),
                    best_trip=BestTrip.model_validate_json(snapshot["best_trip"]),
                    simulated=bool(snapshot["simulated"]),
                )
                for snapshot in snapshot_rows
            ],
        )
