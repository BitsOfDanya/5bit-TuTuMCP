from __future__ import annotations

from datetime import date
from typing import Protocol

from app.ai.parser import (
    TripUpdateParser,
    get_trip_update_parser,
)
from app.models.journey import (
    JourneyOption,
)
from app.models.rescue import (
    TripField,
)
from app.models.trip import (
    TripSpec,
)
from app.rescue.diff import (
    build_trip_diff,
)
from app.rescue.feasibility import (
    journey_satisfies_trip,
)
from app.whatif.analyzer import (
    rank_whatif_candidates,
)
from app.whatif.models import (
    WhatIfResult,
    WhatIfStatus,
)


class WhatIfCandidateProvider(
    Protocol
):
    async def search_alternatives(
        self,
        *,
        trip: TripSpec,
        current_journey: JourneyOption,
        changed_fields: list[
            TripField
        ],
        limit: int = 30,
    ) -> list[
        JourneyOption
    ]:
        ...


class WhatIfEngine:
    """
    Stateless hypothetical scenario engine.

    Important:

    - does not save TripSpec;
    - does not save Journey;
    - does not update preferences;
    - does not accept a candidate;
    - does not mutate the input objects.

    It only answers:

        "What would become possible if these conditions
         were different?"
    """

    def __init__(
        self,
        *,
        provider: (
            WhatIfCandidateProvider
            | None
        ) = None,
        parser: (
            TripUpdateParser
            | None
        ) = None,
        search_limit: int = 30,
        result_limit: int = 5,
    ) -> None:
        if provider is None:
            from app.tutu.whatif_provider import (
                WhatIfTutuProvider,
            )

            provider = (
                WhatIfTutuProvider()
            )

        self.provider = provider

        self.parser = (
            parser
            or get_trip_update_parser()
        )

        self.search_limit = max(
            1,
            search_limit,
        )

        self.result_limit = max(
            1,
            result_limit,
        )

    async def simulate_from_text(
        self,
        *,
        current_trip: TripSpec,
        current_journey: JourneyOption,
        message: str,
        reference_date: date,
    ) -> WhatIfResult:
        hypothetical_trip = (
            await self.parser.parse(
                previous_trip=(
                    current_trip
                ),
                message=message,
                reference_date=(
                    reference_date
                ),
            )
        )

        return await (
            self.simulate_from_spec(
                current_trip=(
                    current_trip
                ),
                hypothetical_trip=(
                    hypothetical_trip
                ),
                current_journey=(
                    current_journey
                ),
            )
        )

    async def simulate_from_spec(
        self,
        *,
        current_trip: TripSpec,
        hypothetical_trip: TripSpec,
        current_journey: JourneyOption,
    ) -> WhatIfResult:
        # Deep copies make the non-mutating contract
        # explicit and testable.
        current_trip_snapshot = (
            current_trip.model_copy(
                deep=True
            )
        )

        hypothetical_snapshot = (
            hypothetical_trip.model_copy(
                deep=True
            )
        )

        journey_snapshot = (
            current_journey.model_copy(
                deep=True
            )
        )

        diff = build_trip_diff(
            previous=(
                current_trip_snapshot
            ),
            updated=(
                hypothetical_snapshot
            ),
        )

        changed_fields = list(
            diff.changed_fields
        )

        material_fields = [
            field
            for field
            in changed_fields
            if field
            != TripField.HARD_CONSTRAINTS
        ]

        baseline_valid = (
            journey_satisfies_trip(
                trip=(
                    hypothetical_snapshot
                ),
                journey=(
                    journey_snapshot
                ),
            )
        )

        if not material_fields:
            return WhatIfResult(
                status=(
                    WhatIfStatus
                    .NO_DIFFERENCE
                ),
                current_trip=(
                    current_trip_snapshot
                ),
                hypothetical_trip=(
                    hypothetical_snapshot
                ),
                baseline_journey=(
                    journey_snapshot
                ),
                changed_fields=(
                    changed_fields
                ),
                baseline_valid=(
                    baseline_valid
                ),
                candidates=[],
            )

        journeys = (
            await self
            .provider
            .search_alternatives(
                trip=(
                    hypothetical_snapshot
                ),
                current_journey=(
                    journey_snapshot
                ),
                changed_fields=(
                    changed_fields
                ),
                limit=(
                    self.search_limit
                ),
            )
        )

        candidates = (
            rank_whatif_candidates(
                current=(
                    journey_snapshot
                ),
                journeys=journeys,
                limit=(
                    self.result_limit
                ),
            )
        )

        status = (
            WhatIfStatus
            .ALTERNATIVES_FOUND
            if candidates
            else WhatIfStatus
            .NO_ALTERNATIVES
        )

        return WhatIfResult(
            status=status,
            current_trip=(
                current_trip_snapshot
            ),
            hypothetical_trip=(
                hypothetical_snapshot
            ),
            baseline_journey=(
                journey_snapshot
            ),
            changed_fields=(
                changed_fields
            ),
            baseline_valid=(
                baseline_valid
            ),
            candidates=candidates,
        )