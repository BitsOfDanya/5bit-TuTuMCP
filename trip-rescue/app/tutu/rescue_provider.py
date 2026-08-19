from __future__ import annotations

from typing import Protocol

from app.models.journey import (
    HotelOption,
    JourneyOption,
    TransportSegment,
)
from app.models.rescue import (
    RescueCandidate,
    RescueComponent,
    RescueExecutionResult,
    RescuePlanningResult,
    RescueSearchPlan,
)
from app.models.trip import TripSpec
from app.rescue.fallback import (
    evaluate_soft_relaxations,
)
from app.rescue.feasibility import (
    journey_satisfies_trip,
)


class JourneyCandidateProvider(
    Protocol
):
    async def search_candidates(
        self,
        trip: TripSpec,
    ) -> list[JourneyOption]:
        ...


class SelectiveCandidateProvider(
    Protocol
):
    async def search_outbound(
        self,
        *,
        trip: TripSpec,
    ) -> list[TransportSegment]:
        ...

    async def search_inbound(
        self,
        *,
        trip: TripSpec,
    ) -> list[TransportSegment]:
        ...

    async def search_hotel(
        self,
        *,
        trip: TripSpec,
        current_journey: JourneyOption,
    ) -> HotelOption | None:
        ...


class RescueTutuProvider:
    def __init__(
        self,
        journey_provider: (
            JourneyCandidateProvider
            | None
        ) = None,
        selective_provider: (
            SelectiveCandidateProvider
            | None
        ) = None,
    ) -> None:
        production_defaults = (
            journey_provider is None
        )

        if journey_provider is None:
            from app.tutu.provider import (
                TutuMCPJourneyProvider,
            )

            journey_provider = (
                TutuMCPJourneyProvider()
            )

        self.journey_provider = (
            journey_provider
        )

        if (
            selective_provider is None
            and production_defaults
        ):
            from app.tutu.selective_provider import (
                TutuSelectiveProvider,
            )

            full_provider = (
                self.journey_provider
            )

            selective_provider = (
                TutuSelectiveProvider(
                    client=getattr(
                        full_provider,
                        "client",
                        None,
                    ),
                    normalizer=getattr(
                        full_provider,
                        "normalizer",
                        None,
                    ),
                    hotel_provider=getattr(
                        full_provider,
                        "hotel_provider",
                        None,
                    ),
                )
            )

        self.selective_provider = (
            selective_provider
        )

    async def search_replans(
        self,
        *,
        trip: TripSpec,
        current_journey: JourneyOption,
        planning: RescuePlanningResult,
        limit: int = 5,
    ) -> RescueExecutionResult:

        if (
            planning.status
            == "no_change"
        ):
            return RescueExecutionResult(
                status="no_change",
                candidates=[],
            )

        if not planning.plans:
            return RescueExecutionResult(
                status="no_candidates",
                candidates=[],
            )

        exact_candidates: list[
            RescueCandidate
        ] = []

        fallback_candidates: list[
            RescueCandidate
        ] = []

        seen_exact: set[
            tuple[
                str,
                str,
                str | None,
                str,
            ]
        ] = set()

        seen_fallback: set[
            tuple[
                str,
                str,
                str | None,
                str,
            ]
        ] = set()

        broad_candidates: (
            list[JourneyOption]
            | None
        ) = None

        for plan in planning.plans:
            merged_journeys: list[
                JourneyOption
            ]

            if (
                len(
                    plan.replace_components
                )
                == 1
                and self.selective_provider
                is not None
            ):
                merged_journeys = (
                    await self
                    ._execute_selective_plan(
                        trip=trip,
                        current_journey=(
                            current_journey
                        ),
                        plan=plan,
                    )
                )

            else:
                if broad_candidates is None:
                    broad_candidates = (
                        await self
                        .journey_provider
                        .search_candidates(
                            trip
                        )
                    )

                merged_journeys = [
                    merged
                    for external
                    in broad_candidates
                    if (
                        merged := (
                            _merge_journey(
                                current=(
                                    current_journey
                                ),
                                external=(
                                    external
                                ),
                                plan=plan,
                            )
                        )
                    )
                    is not None
                ]

            for merged in merged_journeys:
                signature = (
                    plan.id,
                    merged.outbound.id,
                    (
                        merged.hotel.id
                        if merged.hotel
                        is not None
                        else None
                    ),
                    merged.inbound.id,
                )

                # ---------------------------------------------
                # Exact candidate
                # ---------------------------------------------

                if (
                    journey_satisfies_trip(
                        trip=trip,
                        journey=merged,
                    )
                ):
                    if (
                        signature
                        in seen_exact
                    ):
                        continue

                    seen_exact.add(
                        signature
                    )

                    exact_candidates.append(
                        _build_exact_candidate(
                            plan=plan,
                            current=(
                                current_journey
                            ),
                            merged=merged,
                        )
                    )

                    continue

                # ---------------------------------------------
                # Negotiation fallback
                # ---------------------------------------------

                evaluation = (
                    evaluate_soft_relaxations(
                        trip=trip,
                        journey=merged,
                    )
                )

                if evaluation is None:
                    continue

                if (
                    signature
                    in seen_fallback
                ):
                    continue

                seen_fallback.add(
                    signature
                )

                fallback_candidates.append(
                    _build_fallback_candidate(
                        plan=plan,
                        current=(
                            current_journey
                        ),
                        merged=merged,
                        relaxation_score=(
                            evaluation.score
                        ),
                        relaxations=list(
                            evaluation.relaxations
                        ),
                        suggested_trip=(
                            evaluation
                            .suggested_trip
                        ),
                    )
                )

        # Exact always wins.
        if exact_candidates:
            return RescueExecutionResult(
                status="candidates_found",
                candidates=(
                    _select_diverse_candidates(
                        candidates=(
                            exact_candidates
                        ),
                        limit=limit,
                    )
                ),
            )

        # Only if exact solution doesn't exist do we expose
        # the closest soft compromises.
        if fallback_candidates:
            return RescueExecutionResult(
                status=(
                    "negotiation_required"
                ),
                candidates=(
                    _select_diverse_candidates(
                        candidates=(
                            fallback_candidates
                        ),
                        limit=limit,
                    )
                ),
            )

        return RescueExecutionResult(
            status="no_candidates",
            candidates=[],
        )

    async def _execute_selective_plan(
        self,
        *,
        trip: TripSpec,
        current_journey: JourneyOption,
        plan: RescueSearchPlan,
    ) -> list[JourneyOption]:

        if self.selective_provider is None:
            return []

        component = (
            plan.replace_components[0]
        )

        if (
            component
            == RescueComponent.INBOUND
        ):
            segments = (
                await self
                .selective_provider
                .search_inbound(
                    trip=trip
                )
            )

            return [
                _assemble_journey(
                    outbound=(
                        current_journey
                        .outbound
                    ),
                    hotel=(
                        current_journey
                        .hotel
                    ),
                    inbound=segment,
                )
                for segment
                in segments
            ]

        if (
            component
            == RescueComponent.OUTBOUND
        ):
            segments = (
                await self
                .selective_provider
                .search_outbound(
                    trip=trip
                )
            )

            return [
                _assemble_journey(
                    outbound=segment,
                    hotel=(
                        current_journey
                        .hotel
                    ),
                    inbound=(
                        current_journey
                        .inbound
                    ),
                )
                for segment
                in segments
            ]

        if (
            component
            == RescueComponent.HOTEL
        ):
            hotel = (
                await self
                .selective_provider
                .search_hotel(
                    trip=trip,
                    current_journey=(
                        current_journey
                    ),
                )
            )

            if hotel is None:
                return []

            return [
                _assemble_journey(
                    outbound=(
                        current_journey
                        .outbound
                    ),
                    hotel=hotel,
                    inbound=(
                        current_journey
                        .inbound
                    ),
                )
            ]

        return []


def _merge_journey(
    *,
    current: JourneyOption,
    external: JourneyOption,
    plan: RescueSearchPlan,
) -> JourneyOption | None:

    replacing = set(
        plan.replace_components
    )

    outbound = (
        external.outbound
        if (
            RescueComponent.OUTBOUND
            in replacing
        )
        else current.outbound
    )

    inbound = (
        external.inbound
        if (
            RescueComponent.INBOUND
            in replacing
        )
        else current.inbound
    )

    if (
        RescueComponent.HOTEL
        in replacing
    ):
        if (
            current.hotel is not None
            and external.hotel is None
        ):
            return None

        hotel = external.hotel

    else:
        hotel = current.hotel

    return _assemble_journey(
        outbound=outbound,
        hotel=hotel,
        inbound=inbound,
    )


def _assemble_journey(
    *,
    outbound: TransportSegment,
    hotel: HotelOption | None,
    inbound: TransportSegment,
) -> JourneyOption:

    hotel_price = (
        hotel.price
        if hotel is not None
        else 0
    )

    total_price = (
        outbound.price
        + hotel_price
        + inbound.price
    )

    hotel_id = (
        hotel.id
        if hotel is not None
        else "no-hotel"
    )

    return JourneyOption(
        id=(
            "rescued:"
            f"{outbound.id}:"
            f"{hotel_id}:"
            f"{inbound.id}"
        ),
        outbound=outbound,
        hotel=hotel,
        inbound=inbound,
        total_price=total_price,
    )


def _build_exact_candidate(
    *,
    plan: RescueSearchPlan,
    current: JourneyOption,
    merged: JourneyOption,
) -> RescueCandidate:

    price_delta = (
        merged.total_price
        - current.total_price
    )

    return RescueCandidate(
        id=(
            "rescue:"
            f"{plan.id}:"
            f"{merged.id}"
        ),
        search_plan_id=plan.id,
        replaced_components=(
            plan.replace_components
        ),
        preserved_components=(
            plan.preserve_components
        ),
        journey=merged,
        previous_total_price=(
            current.total_price
        ),
        new_total_price=(
            merged.total_price
        ),
        price_delta=price_delta,
        score=(
            _candidate_score(
                plan=plan,
                current=current,
                merged=merged,
                price_delta=(
                    price_delta
                ),
            )
        ),
        exact=True,
        relaxations=[],
        suggested_trip=None,
    )


def _build_fallback_candidate(
    *,
    plan: RescueSearchPlan,
    current: JourneyOption,
    merged: JourneyOption,
    relaxation_score: float,
    relaxations,
    suggested_trip: TripSpec,
) -> RescueCandidate:

    price_delta = (
        merged.total_price
        - current.total_price
    )

    base_score = (
        _candidate_score(
            plan=plan,
            current=current,
            merged=merged,
            price_delta=(
                price_delta
            ),
        )
    )

    return RescueCandidate(
        id=(
            "rescue-negotiation:"
            f"{plan.id}:"
            f"{merged.id}"
        ),
        search_plan_id=plan.id,
        replaced_components=(
            plan.replace_components
        ),
        preserved_components=(
            plan.preserve_components
        ),
        journey=merged,
        previous_total_price=(
            current.total_price
        ),
        new_total_price=(
            merged.total_price
        ),
        price_delta=price_delta,
        score=round(
            base_score
            + relaxation_score,
            6,
        ),
        exact=False,
        relaxations=relaxations,
        suggested_trip=(
            suggested_trip
        ),
    )


def _candidate_score(
    *,
    plan: RescueSearchPlan,
    current: JourneyOption,
    merged: JourneyOption,
    price_delta: int,
) -> float:

    positive_price_delta = max(
        price_delta,
        0,
    )

    price_penalty = (
        positive_price_delta
        / max(
            current.total_price,
            1,
        )
    )

    schedule_shift_minutes = 0

    replacing = set(
        plan.replace_components
    )

    if (
        RescueComponent.OUTBOUND
        in replacing
    ):
        schedule_shift_minutes += int(
            abs(
                (
                    merged.outbound.departure
                    - current.outbound.departure
                ).total_seconds()
            )
            // 60
        )

    if (
        RescueComponent.INBOUND
        in replacing
    ):
        schedule_shift_minutes += int(
            abs(
                (
                    merged.inbound.arrival
                    - current.inbound.arrival
                ).total_seconds()
            )
            // 60
        )

    schedule_penalty = (
        schedule_shift_minutes
        / 1440
        * 0.15
    )

    return round(
        plan.score
        + schedule_penalty
        + price_penalty,
        6,
    )


def _select_diverse_candidates(
    *,
    candidates: list[
        RescueCandidate
    ],
    limit: int,
) -> list[
    RescueCandidate
]:
    ordered = sorted(
        candidates,
        key=lambda item: (
            item.score,
            len(
                item.relaxations
            ),
            len(
                item.replaced_components
            ),
            item.new_total_price,
            item.id,
        ),
    )

    selected: list[
        RescueCandidate
    ] = []

    selected_ids: set[
        str
    ] = set()

    used_plans: set[
        str
    ] = set()

    for candidate in ordered:
        if (
            candidate.search_plan_id
            in used_plans
        ):
            continue

        selected.append(
            candidate
        )

        selected_ids.add(
            candidate.id
        )

        used_plans.add(
            candidate.search_plan_id
        )

        if len(selected) >= limit:
            return selected

    for candidate in ordered:
        if (
            candidate.id
            in selected_ids
        ):
            continue

        selected.append(
            candidate
        )

        selected_ids.add(
            candidate.id
        )

        if len(selected) >= limit:
            break

    return selected