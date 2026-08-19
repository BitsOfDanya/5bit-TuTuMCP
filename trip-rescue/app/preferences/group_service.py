from __future__ import annotations

from functools import lru_cache

from pydantic import (
    BaseModel,
    Field,
)

from app.models.journey import (
    JourneyOption,
)
from app.preferences.group import (
    GroupPreferenceSummary,
    build_group_preference_profile,
)
from app.preferences.scorer import (
    rerank_journeys,
)
from app.preferences.store import (
    PreferenceStore,
    get_preference_store,
)


class MissingGroupProfilesError(
    ValueError
):
    def __init__(
        self,
        profile_ids: list[str],
    ) -> None:
        self.profile_ids = (
            profile_ids
        )

        super().__init__(
            "Preference profiles not found: "
            + ", ".join(
                profile_ids
            )
        )


class GroupRerankItem(
    BaseModel
):
    candidate_id: str

    rank_before: int = Field(
        ge=1
    )

    rank_after: int = Field(
        ge=1
    )

    preference_score: float

    reasons: list[
        str
    ] = Field(
        default_factory=list
    )


class GroupRerankResult(
    BaseModel
):
    group: GroupPreferenceSummary

    items: list[
        GroupRerankItem
    ]


class GroupPreferenceService:
    def __init__(
        self,
        *,
        store: (
            PreferenceStore
            | None
        ) = None,
    ) -> None:
        self.store = (
            store
            or get_preference_store()
        )

    def build_profile(
        self,
        *,
        group_id: str,
        profile_ids: list[str],
    ) -> GroupPreferenceSummary:
        profiles = (
            self._resolve_profiles(
                profile_ids
            )
        )

        return (
            build_group_preference_profile(
                group_id=group_id,
                profiles=profiles,
            )
        )

    def rerank(
        self,
        *,
        group_id: str,
        profile_ids: list[str],
        journeys: list[
            JourneyOption
        ],
    ) -> GroupRerankResult:
        if not journeys:
            raise ValueError(
                "At least one candidate "
                "is required"
            )

        group = (
            self.build_profile(
                group_id=group_id,
                profile_ids=(
                    profile_ids
                ),
            )
        )

        ranked = rerank_journeys(
            journeys=journeys,
            profile=group.profile,
        )

        return GroupRerankResult(
            group=group,
            items=[
                GroupRerankItem(
                    candidate_id=(
                        item.journey.id
                    ),
                    rank_before=(
                        item.rank_before
                    ),
                    rank_after=(
                        item.rank_after
                    ),
                    preference_score=(
                        item.preference_score
                    ),
                    reasons=(
                        _group_reasons(
                            original_reasons=(
                                list(
                                    item.reasons
                                )
                            ),
                            group=group,
                        )
                    ),
                )
                for item
                in ranked
            ],
        )

    def _resolve_profiles(
        self,
        profile_ids: list[str],
    ):
        clean_ids: list[str] = []

        seen: set[str] = set()

        for value in profile_ids:
            clean = value.strip()

            if not clean:
                raise ValueError(
                    "profile_id cannot "
                    "be empty"
                )

            if clean in seen:
                continue

            seen.add(
                clean
            )

            clean_ids.append(
                clean
            )

        if len(clean_ids) < 2:
            raise ValueError(
                "At least two unique "
                "profile_ids are required"
            )

        profiles = []

        missing: list[str] = []

        for profile_id in (
            clean_ids
        ):
            profile = self.store.get(
                profile_id
            )

            if profile is None:
                missing.append(
                    profile_id
                )

                continue

            profiles.append(
                profile
            )

        if missing:
            raise (
                MissingGroupProfilesError(
                    missing
                )
            )

        return profiles


def _group_reasons(
    *,
    original_reasons: list[str],
    group: GroupPreferenceSummary,
) -> list[str]:
    result: list[str] = []

    seen: set[str] = set()

    for value in (
        original_reasons
        + group.highlights
    ):
        clean = value.strip()

        if (
            not clean
            or clean in seen
        ):
            continue

        seen.add(
            clean
        )

        result.append(
            clean
        )

    return result


@lru_cache(maxsize=1)
def get_group_preference_service(
) -> GroupPreferenceService:
    return GroupPreferenceService()