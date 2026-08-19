from __future__ import annotations

import json
import os

from functools import lru_cache
from pathlib import Path
from threading import RLock

from app.preferences.models import (
    PreferenceProfile,
)


DEFAULT_PREFERENCE_STORE_PATH = (
    "./data/preferences.json"
)


class PreferenceStore:
    """
    Preference profile storage.

    Behaviour:

    PreferenceStore()
        -> isolated in-memory store.

    PreferenceStore("/path/file.json")
        -> persistent JSON store.

    Production code should normally use:

        get_preference_store()

    which resolves PREFERENCE_STORE_PATH and falls back to:

        ./data/preferences.json

    Docker overrides it with:

        /data/preferences.json
    """

    def __init__(
        self,
        persist_path: str | None = None,
    ) -> None:
        self._lock = RLock()

        self._profiles: dict[
            str,
            PreferenceProfile,
        ] = {}

        clean_path = (
            persist_path.strip()
            if persist_path
            else ""
        )

        self._persist_path = (
            Path(clean_path)
            if clean_path
            else None
        )

        self._load()

    @property
    def persist_path(
        self,
    ) -> Path | None:
        return self._persist_path

    @property
    def persistent(
        self,
    ) -> bool:
        return (
            self._persist_path
            is not None
        )

    def get(
        self,
        profile_id: str,
    ) -> PreferenceProfile | None:
        clean_id = (
            _clean_profile_id(
                profile_id
            )
        )

        with self._lock:
            profile = (
                self._profiles.get(
                    clean_id
                )
            )

            if profile is None:
                return None

            return profile.model_copy(
                deep=True
            )

    def get_or_create(
        self,
        profile_id: str,
    ) -> PreferenceProfile:
        clean_id = (
            _clean_profile_id(
                profile_id
            )
        )

        with self._lock:
            existing = (
                self._profiles.get(
                    clean_id
                )
            )

            if existing is not None:
                return existing.model_copy(
                    deep=True
                )

            profile = (
                PreferenceProfile(
                    profile_id=clean_id
                )
            )

            self._profiles[
                clean_id
            ] = profile

            self._persist()

            return profile.model_copy(
                deep=True
            )

    def save(
        self,
        profile: PreferenceProfile,
    ) -> PreferenceProfile:
        clean_id = (
            _clean_profile_id(
                profile.profile_id
            )
        )

        saved = (
            profile.model_copy(
                deep=True,
                update={
                    "profile_id": clean_id
                },
            )
        )

        with self._lock:
            self._profiles[
                clean_id
            ] = saved

            self._persist()

        return saved.model_copy(
            deep=True
        )

    def reset(
        self,
        profile_id: str,
    ) -> bool:
        clean_id = (
            _clean_profile_id(
                profile_id
            )
        )

        with self._lock:
            existed = (
                clean_id
                in self._profiles
            )

            self._profiles.pop(
                clean_id,
                None,
            )

            if existed:
                self._persist()

            return existed

    def clear(
        self,
    ) -> None:
        with self._lock:
            self._profiles.clear()

            self._persist()

    def count(
        self,
    ) -> int:
        with self._lock:
            return len(
                self._profiles
            )

    def list_profiles(
        self,
    ) -> list[
        PreferenceProfile
    ]:
        with self._lock:
            return [
                profile.model_copy(
                    deep=True
                )
                for profile
                in self._profiles.values()
            ]

    def _load(
        self,
    ) -> None:
        path = (
            self._persist_path
        )

        if path is None:
            return

        if not path.exists():
            return

        try:
            text = path.read_text(
                encoding="utf-8"
            )

            if not text.strip():
                return

            raw = json.loads(
                text
            )

            if not isinstance(
                raw,
                dict,
            ):
                return

            profiles: dict[
                str,
                PreferenceProfile,
            ] = {}

            for (
                profile_id,
                payload,
            ) in raw.items():
                if not isinstance(
                    payload,
                    dict,
                ):
                    continue

                try:
                    clean_id = (
                        _clean_profile_id(
                            str(
                                profile_id
                            )
                        )
                    )

                    profile = (
                        PreferenceProfile
                        .model_validate(
                            payload
                        )
                    )

                except (
                    ValueError,
                    TypeError,
                ):
                    continue

                except Exception:
                    # One malformed profile must not
                    # make all other profiles unusable.
                    continue

                profiles[
                    clean_id
                ] = (
                    profile.model_copy(
                        deep=True,
                        update={
                            "profile_id": (
                                clean_id
                            )
                        },
                    )
                )

            self._profiles = (
                profiles
            )

        except (
            OSError,
            json.JSONDecodeError,
        ):
            # Preference profiles are auxiliary runtime
            # state. Corruption must not prevent
            # Trip Rescue from starting.
            self._profiles = {}

    def _persist(
        self,
    ) -> None:
        path = (
            self._persist_path
        )

        if path is None:
            return

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = {
            profile_id: (
                profile.model_dump(
                    mode="json"
                )
            )
            for (
                profile_id,
                profile,
            )
            in sorted(
                self._profiles.items(),
                key=lambda item: (
                    item[0]
                ),
            )
        }

        serialized = (
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            )
        )

        temporary = (
            path.with_name(
                f"{path.name}.tmp"
            )
        )

        temporary.write_text(
            serialized,
            encoding="utf-8",
        )

        # Atomic replacement on the same filesystem.
        temporary.replace(
            path
        )


def _clean_profile_id(
    value: str,
) -> str:
    clean = (
        value.strip()
    )

    if not clean:
        raise ValueError(
            "profile_id cannot be empty"
        )

    if len(clean) > 128:
        raise ValueError(
            "profile_id is too long"
        )

    return clean


def _resolve_persist_path() -> (
    str
    | None
):
    """
    Resolve persistence path for the application singleton.

    Environment variable wins.

    Missing variable:
        ./data/preferences.json

    Empty variable:
        persistence explicitly disabled.
    """

    value = os.getenv(
        "PREFERENCE_STORE_PATH"
    )

    if value is None:
        return (
            DEFAULT_PREFERENCE_STORE_PATH
        )

    clean = (
        value.strip()
    )

    if not clean:
        return None

    return clean


@lru_cache(maxsize=1)
def get_preference_store() -> (
    PreferenceStore
):
    """
    Application-level persistent singleton.

    Tests that need isolation should instantiate:

        PreferenceStore()

    directly.
    """

    return PreferenceStore(
        persist_path=(
            _resolve_persist_path()
        )
    )