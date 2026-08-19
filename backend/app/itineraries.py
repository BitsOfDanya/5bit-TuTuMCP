from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AcceptedItineraryRecord


class AcceptedItineraryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: str) -> AcceptedItineraryRecord | None:
        result = await self._session.execute(
            select(AcceptedItineraryRecord).where(AcceptedItineraryRecord.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def save(
        self,
        *,
        user_id: str,
        trip_spec: dict[str, object],
        journey: dict[str, object],
    ) -> AcceptedItineraryRecord:
        record = await self.get(user_id)
        if record is None:
            record = AcceptedItineraryRecord(
                user_id=user_id,
                trip_spec=trip_spec,
                journey=journey,
            )
            self._session.add(record)
        else:
            record.trip_spec = trip_spec
            record.journey = journey
        await self._session.commit()
        await self._session.refresh(record)
        return record
