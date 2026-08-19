from __future__ import annotations

from app.api.schemas import (
    PublicRescueResponse,
    RawRescueResponse,
)
from app.explanations.engine import (
    build_decision_explanation,
)
from app.models.journey import (
    JourneyOption,
)
from app.rescue.insights import (
    build_rescue_insights,
)


def attach_rescue_explanations(
    *,
    public: PublicRescueResponse,
    result: RawRescueResponse,
    baseline_journey: JourneyOption,
) -> PublicRescueResponse:
    """
    Attach Decision Explanation to already created
    public Rescue candidates.

    Ranking and domain candidates are untouched.
    """

    domain_candidates = {
        candidate.id: candidate
        for candidate
        in result.execution.candidates
    }

    for public_candidate in (
        public.candidates
    ):
        domain = (
            domain_candidates.get(
                public_candidate.id
            )
        )

        if domain is None:
            continue

        preference_reasons: list[
            str
        ] = []

        if (
            public_candidate.personalization
            is not None
        ):
            preference_reasons = list(
                public_candidate
                .personalization
                .reasons
            )

        raw_insights = (
            build_rescue_insights(
                journey=domain.journey
            )
        )

        insight_reasons = [
            insight.description
            for insight
            in raw_insights
        ]

        tradeoff_reasons = [
            relaxation.description
            for relaxation
            in domain.relaxations
        ]

        public_candidate.explanation = (
            build_decision_explanation(
                trip=(
                    result.updated_trip
                ),
                baseline=(
                    baseline_journey
                ),
                candidate=(
                    domain.journey
                ),
                preserved_components=list(
                    domain
                    .preserved_components
                ),
                changed_components=list(
                    domain
                    .replaced_components
                ),
                preference_reasons=(
                    preference_reasons
                ),
                insight_reasons=(
                    insight_reasons
                ),
                tradeoff_reasons=(
                    tradeoff_reasons
                ),
            )
        )

    return public