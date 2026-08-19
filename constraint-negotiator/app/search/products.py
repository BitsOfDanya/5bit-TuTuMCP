from __future__ import annotations

import asyncio
from typing import Any

from app.api.schemas import (
    ProductSearchRequest,
    PublicHotelOption,
    PublicProductSearchOption,
    PublicProductSearchResult,
    PublicTransportSegment,
)
from app.models.journey import HotelOption, TransportSegment
from app.tutu.client import TutuMCPClient
from app.tutu.hotel_provider import TutuHotelProvider
from app.tutu.normalizer import TutuSearchNormalizer


class ProductSearchService:
    """Route each product to its dedicated Tutu MCP search tool."""

    def __init__(
        self,
        client: TutuMCPClient | None = None,
        transport_normalizer: TutuSearchNormalizer | None = None,
        hotel_provider: TutuHotelProvider | None = None,
    ) -> None:
        self.client = client or TutuMCPClient()
        self.transport_normalizer = transport_normalizer or TutuSearchNormalizer()
        self.hotel_provider = hotel_provider or TutuHotelProvider(client=self.client)

    async def search(self, request: ProductSearchRequest) -> PublicProductSearchResult:
        if request.service_type == "hotel":
            return await self._search_hotels(request)
        return await self._search_transport(request)

    async def _search_transport(
        self,
        request: ProductSearchRequest,
    ) -> PublicProductSearchResult:
        if not request.origin:
            raise ValueError("origin is required for transport search")

        tool_name = {
            "train": "search_rail",
            "flight": "search_avia",
            "bus": "search_bus",
        }[request.service_type]
        arguments: dict[str, Any] = {
            "origin": request.origin,
            "destination": request.destination,
            "departure_date": request.start_date.isoformat(),
            "page": 1,
            "page_size": 10,
            "sort": "price_asc",
            "price_max": request.budget,
            "direct_only": False,
            "view": "compact",
        }
        if request.service_type == "train":
            arguments["passengers"] = request.travelers
        else:
            arguments["adults"] = request.travelers
        if request.service_type == "flight" and request.end_date:
            arguments["return_date"] = request.end_date.isoformat()

        payload = await self.client.call_tool(name=tool_name, arguments=arguments)
        segments = self.transport_normalizer.normalize_search_result(
            payload=payload,
            travelers=request.travelers,
        )
        segments = [
            segment
            for segment in segments
            if segment.mode.value == request.service_type
            and (
                request.preferred_time is None
                or segment.departure.timetz().replace(tzinfo=None)
                >= request.preferred_time.replace(tzinfo=None)
            )
        ][:3]
        checkout_urls = await asyncio.gather(
            *(self._checkout_url(segment) for segment in segments)
        )
        options = [
            self._transport_option(segment, checkout_url)
            for segment, checkout_url in zip(segments, checkout_urls)
        ]
        return PublicProductSearchResult(
            status="success" if options else "no_options",
            options=options,
        )

    async def _search_hotels(
        self,
        request: ProductSearchRequest,
    ) -> PublicProductSearchResult:
        if request.end_date is None:
            raise ValueError("end_date is required for hotel search")
        hotels = await self.hotel_provider.search_options(
            city=request.destination,
            check_in=request.start_date,
            check_out=request.end_date,
            travelers=request.travelers,
        )
        if request.budget is not None:
            hotels = [hotel for hotel in hotels if hotel.price <= request.budget]
        options = [self._hotel_option(hotel) for hotel in hotels[:3]]
        return PublicProductSearchResult(
            status="success" if options else "no_options",
            options=options,
        )

    async def _checkout_url(self, segment: TransportSegment) -> str | None:
        if segment.checkout_ref:
            try:
                payload = await self.client.call_tool(
                    name="create_checkout_link",
                    arguments=segment.checkout_ref,
                )
            except RuntimeError:
                payload = {}
            for key in ("checkout_url", "deeplink", "url"):
                value = payload.get(key)
                if isinstance(value, str) and value:
                    return value
        return segment.booking_url or segment.search_results_url

    @staticmethod
    def _transport_option(
        segment: TransportSegment,
        checkout_url: str | None,
    ) -> PublicProductSearchOption:
        return PublicProductSearchOption(
            id=segment.id,
            title=f"{segment.origin} — {segment.destination}",
            total_price=segment.price,
            currency=segment.currency,
            outbound=PublicTransportSegment.model_validate(
                segment.model_dump(mode="json")
            ),
            action_url=checkout_url,
        )

    @staticmethod
    def _hotel_option(hotel: HotelOption) -> PublicProductSearchOption:
        return PublicProductSearchOption(
            id=hotel.id,
            title=hotel.name,
            total_price=hotel.price,
            currency=hotel.currency,
            hotel=PublicHotelOption.model_validate(hotel.model_dump(mode="json")),
            action_url=hotel.booking_url,
        )
