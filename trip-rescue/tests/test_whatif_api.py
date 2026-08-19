from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import (
    TestClient,
)

import app.api.whatif as whatif_api

from app.models.journey import (
    HotelOption,
    JourneyOption,
    TransportSegment,
)
from app.models.rescue import (
    RescueComponent,
    TripField,
)
from app.models.trip import (
    ConstraintField,
    TransportMode,
    TripSpec,
)
from app.whatif.analyzer import (
    rank_whatif_candidates,
)
from app.whatif.models import (
    WhatIfResult,
    WhatIfStatus,
)


def _trip(
    return_before: str,
) -> TripSpec:
    return TripSpec(
        origin="Москва",
        destination="Казань",
        outbound_date="2026-08-21",
        return_date="2026-08-23",
        outbound_after="19:00:00",
        return_before=return_before,
        travelers=1,
        budget=30_000,
        excluded_transport=[],
        preferred_transport=[],
        max_transfers=None,
        hard_constraints=[
            ConstraintField.RETURN_BEFORE
        ],
    )


def _segment(
    *,
    segment_id: str,
    mode: TransportMode,
    origin: str,
    destination: str,
    departure: str,
    arrival: str,
    price: int,
) -> TransportSegment:
    return TransportSegment(
        id=segment_id,
        mode=mode,
        origin=origin,
        destination=destination,
        departure=(
            datetime.fromisoformat(
                departure
            )
        ),
        arrival=(
            datetime.fromisoformat(
                arrival
            )
        ),
        price=price,
        transfers=0,
    )


def _baseline() -> JourneyOption:
    outbound = _segment(
        segment_id="out-current",
        mode=TransportMode.BUS,
        origin="Москва",
        destination="Казань",
        departure=(
            "2026-08-21"
            "T22:00:00+03:00"
        ),
        arrival=(
            "2026-08-22"
            "T08:00:00+03:00"
        ),
        price=5_000,
    )

    inbound = _segment(
        segment_id="in-current",
        mode=TransportMode.BUS,
        origin="Казань",
        destination="Москва",
        departure=(
            "2026-08-22"
            "T19:00:00+03:00"
        ),
        arrival=(
            "2026-08-23"
            "T07:00:00+03:00"
        ),
        price=7_000,
    )

    hotel = HotelOption(
        id="hotel-current",
        name="Test Hotel",
        price=3_000,
        rating=8.5,
        check_in="2026-08-22",
        check_out="2026-08-23",
        nights=1,
    )

    return JourneyOption(
        id="baseline",
        outbound=outbound,
        inbound=inbound,
        hotel=hotel,
        total_price=15_000,
    )


def _alternative() -> JourneyOption:
    current = _baseline()

    inbound = _segment(
        segment_id="in-alt",
        mode=TransportMode.TRAIN,
        origin="Казань",
        destination="Москва",
        departure=(
            "2026-08-22"
            "T21:00:00+03:00"
        ),
        arrival=(
            "2026-08-23"
            "T09:30:00+03:00"
        ),
        price=4_000,
    )

    return JourneyOption(
        id="alternative",
        outbound=current.outbound,
        inbound=inbound,
        hotel=current.hotel,
        total_price=12_000,
    )


def _result() -> WhatIfResult:
    current_trip = _trip(
        "08:00:00"
    )

    hypothetical = _trip(
        "10:00:00"
    )

    baseline = _baseline()

    candidates = (
        rank_whatif_candidates(
            current=baseline,
            journeys=[
                _alternative()
            ],
        )
    )

    return WhatIfResult(
        status=(
            WhatIfStatus
            .ALTERNATIVES_FOUND
        ),
        current_trip=current_trip,
        hypothetical_trip=(
            hypothetical
        ),
        baseline_journey=(
            baseline
        ),
        changed_fields=[
            TripField.RETURN_BEFORE
        ],
        baseline_valid=True,
        candidates=candidates,
    )


class FakeWhatIfEngine:
    async def simulate_from_spec(
        self,
        *,
        current_trip,
        hypothetical_trip,
        current_journey,
    ):
        return _result()

    async def simulate_from_text(
        self,
        *,
        current_trip,
        current_journey,
        message,
        reference_date,
    ):
        return _result()


def _client(
    monkeypatch,
) -> TestClient:
    monkeypatch.setattr(
        whatif_api,
        "get_whatif_engine",
        lambda: FakeWhatIfEngine(),
    )

    app = FastAPI()

    app.include_router(
        whatif_api.router
    )

    return TestClient(
        app
    )


def _public_journey_payload() -> dict:
    journey = _baseline()

    return {
        "id": journey.id,
        "total_price": (
            journey.total_price
        ),
        "outbound": {
            "id": (
                journey.outbound.id
            ),
            "mode": (
                journey
                .outbound
                .mode
                .value
            ),
            "origin": (
                journey
                .outbound
                .origin
            ),
            "destination": (
                journey
                .outbound
                .destination
            ),
            "departure": (
                journey
                .outbound
                .departure
                .isoformat()
            ),
            "arrival": (
                journey
                .outbound
                .arrival
                .isoformat()
            ),
            "price": (
                journey
                .outbound
                .price
            ),
            "transfers": 0,
        },
        "inbound": {
            "id": (
                journey.inbound.id
            ),
            "mode": (
                journey
                .inbound
                .mode
                .value
            ),
            "origin": (
                journey
                .inbound
                .origin
            ),
            "destination": (
                journey
                .inbound
                .destination
            ),
            "departure": (
                journey
                .inbound
                .departure
                .isoformat()
            ),
            "arrival": (
                journey
                .inbound
                .arrival
                .isoformat()
            ),
            "price": (
                journey
                .inbound
                .price
            ),
            "transfers": 0,
        },
        "hotel": {
            "id": (
                journey.hotel.id
            ),
            "name": (
                journey.hotel.name
            ),
            "price": (
                journey.hotel.price
            ),
            "rating": (
                journey.hotel.rating
            ),
            "check_in": (
                journey.hotel
                .check_in
                .isoformat()
            ),
            "check_out": (
                journey.hotel
                .check_out
                .isoformat()
            ),
            "nights": 1,
        },
    }


def test_from_spec_public(
    monkeypatch,
) -> None:
    client = _client(
        monkeypatch
    )

    response = client.post(
        (
            "/api/v1/what-if/"
            "from-spec/public"
        ),
        json={
            "current_trip": (
                _trip(
                    "08:00:00"
                )
                .model_dump(
                    mode="json"
                )
            ),
            "hypothetical_trip": (
                _trip(
                    "10:00:00"
                )
                .model_dump(
                    mode="json"
                )
            ),
            "current_journey": (
                _public_journey_payload()
            ),
        },
    )

    assert (
        response.status_code
        == 200
    )

    data = response.json()

    assert (
        data["simulation"]
        is True
    )

    assert (
        data["status"]
        == "alternatives_found"
    )

    assert (
        data["baseline_valid"]
        is True
    )

    assert (
        data[
            "hypothetical_trip"
        ][
            "return_before"
        ]
        == "10:00:00"
    )

    assert (
        len(
            data["candidates"]
        )
        == 1
    )

    candidate = (
        data["candidates"][0]
    )

    assert (
        candidate["rank"]
        == 1
    )

    assert (
        candidate[
            "journey"
        ][
            "total_price"
        ]
        == 12_000
    )

    assert (
        candidate[
            "impact"
        ][
            "savings"
        ]
        == 3_000
    )

    assert (
        candidate[
            "impact"
        ][
            "components_changed"
        ]
        == [
            RescueComponent
            .INBOUND
            .value
        ]
    )


def test_from_text_public(
    monkeypatch,
) -> None:
    client = _client(
        monkeypatch
    )

    response = client.post(
        (
            "/api/v1/what-if/"
            "from-text/public"
        ),
        json={
            "current_trip": (
                _trip(
                    "08:00:00"
                )
                .model_dump(
                    mode="json"
                )
            ),
            "current_journey": (
                _public_journey_payload()
            ),
            "message": (
                "А если можно "
                "вернуться до 10 утра?"
            ),
            "reference_date": (
                "2026-08-19"
            ),
        },
    )

    assert (
        response.status_code
        == 200
    )

    data = response.json()

    assert (
        data["simulation"]
        is True
    )

    assert (
        data["status"]
        == "alternatives_found"
    )


def test_public_response_does_not_commit_state(
    monkeypatch,
) -> None:
    client = _client(
        monkeypatch
    )

    response = client.post(
        (
            "/api/v1/what-if/"
            "from-spec/public"
        ),
        json={
            "current_trip": (
                _trip(
                    "08:00:00"
                )
                .model_dump(
                    mode="json"
                )
            ),
            "hypothetical_trip": (
                _trip(
                    "10:00:00"
                )
                .model_dump(
                    mode="json"
                )
            ),
            "current_journey": (
                _public_journey_payload()
            ),
        },
    )

    data = response.json()

    assert (
        response.status_code
        == 200
    )

    assert (
        data["simulation"]
        is True
    )

    assert (
        "accepted" not in data
    )

    assert (
        "committed" not in data
    )