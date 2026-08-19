from __future__ import annotations

from datetime import date

from app.models.journey import HotelOption
from app.tutu.client import TutuMCPClient
from app.tutu.hotel_normalizer import (
    TutuHotelNormalizer,
)


class TutuHotelProvider:
    def __init__(
        self,
        client: TutuMCPClient | None = None,
        normalizer: TutuHotelNormalizer | None = None,
    ) -> None:
        self.client = (
            client
            or TutuMCPClient()
        )

        self.normalizer = (
            normalizer
            or TutuHotelNormalizer()
        )

    async def search_options(
        self,
        *,
        city: str,
        check_in: date,
        check_out: date,
        travelers: int,
    ) -> list[HotelOption]:

        if check_out <= check_in:
            return []

        payload = await self.client.call_tool(
            name="search_hotels",
            arguments={
                "city_name": city,
                "check_in": (
                    check_in.isoformat()
                ),
                "check_out": (
                    check_out.isoformat()
                ),
                "adults": travelers,
                "page": 1,

                # We intentionally fetch a wider
                # candidate window because the first
                # Tutu row is not necessarily the
                # cheapest hotel.
                "page_size": 30,

                "view": "compact",
            },
        )

        return (
            self.normalizer
            .normalize_search_result(
                payload
            )
        )

    async def get_cheapest_candidate(
        self,
        *,
        city: str,
        check_in: date,
        check_out: date,
        travelers: int,
    ) -> HotelOption | None:

        options = await self.search_options(
            city=city,
            check_in=check_in,
            check_out=check_out,
            travelers=travelers,
        )

        if not options:
            return None

        return options[0]