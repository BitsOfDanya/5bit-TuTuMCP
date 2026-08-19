from typing import Protocol

from app.models.journey import JourneyOption
from app.models.trip import TripSpec


class JourneyProvider(Protocol):
    async def search_candidates(
        self,
        trip: TripSpec,
    ) -> list[JourneyOption]:
        ...