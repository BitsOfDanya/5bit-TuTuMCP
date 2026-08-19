from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from app.models.journey import TransportSegment
from app.models.trip import TransportMode


TRANSPORT_MAPPING: dict[str, TransportMode] = {
    "avia": TransportMode.FLIGHT,
    "railway": TransportMode.TRAIN,
    "bus": TransportMode.BUS,
    "etrain": TransportMode.SUBURBAN_TRAIN,
}


class TutuNormalizationError(ValueError):
    pass


class TutuSearchNormalizer:
    def normalize_search_result(
        self,
        payload: dict[str, Any],
        travelers: int,
    ) -> list[TransportSegment]:

        raw_variants = payload.get(
            "variants",
            []
        )

        if not isinstance(
            raw_variants,
            list,
        ):
            raise TutuNormalizationError(
                "Tutu payload variants is not a list"
            )

        result: list[TransportSegment] = []

        for raw in raw_variants:
            if not isinstance(raw, dict):
                continue

            try:
                segment = self.normalize_offer(
                    raw=raw,
                    travelers=travelers,
                )
            except (
                KeyError,
                TypeError,
                ValueError,
                TutuNormalizationError,
            ):
                # Один плохой upstream offer не должен
                # ломать весь результат поиска.
                continue

            result.append(segment)

        return result

    def normalize_offer(
        self,
        raw: dict[str, Any],
        travelers: int,
    ) -> TransportSegment:

        transport_raw = raw.get(
            "transport"
        )

        mode = TRANSPORT_MAPPING.get(
            str(transport_raw)
        )

        if mode is None:
            raise TutuNormalizationError(
                f"Unsupported transport: "
                f"{transport_raw}"
            )

        offer_id = raw.get(
            "offer_id"
        )

        if not offer_id:
            raise TutuNormalizationError(
                "Offer has no offer_id"
            )

        price_data = raw.get(
            "price"
        )

        if not isinstance(
            price_data,
            dict,
        ):
            raise TutuNormalizationError(
                "Offer has no price"
            )

        source_price = float(
            price_data["amount"]
        )

        currency = str(
            price_data.get(
                "currency",
                "RUB",
            )
        )

        party_price = (
            self._normalize_party_price(
                mode=mode,
                source_price=source_price,
                travelers=travelers,
            )
        )

        departure = datetime.fromisoformat(
            str(raw["departure_at"])
        )

        arrival = datetime.fromisoformat(
            str(raw["arrival_at"])
        )

        legs = raw.get(
            "legs"
        )

        first_leg: dict[str, Any] = {}

        if (
            isinstance(legs, list)
            and legs
            and isinstance(legs[0], dict)
        ):
            first_leg = legs[0]

        origin = str(
            first_leg.get(
                "from",
                "Unknown origin",
            )
        )

        destination = str(
            first_leg.get(
                "to",
                "Unknown destination",
            )
        )

        raw_segments = first_leg.get(
            "segments",
            []
        )

        first_raw_segment: dict[
            str,
            Any,
        ] = {}

        if (
            isinstance(raw_segments, list)
            and raw_segments
            and isinstance(
                raw_segments[0],
                dict,
            )
        ):
            first_raw_segment = (
                raw_segments[0]
            )

        carrier = self._extract_carrier(
            raw=raw,
            first_segment=first_raw_segment,
        )

        voyage_no = first_raw_segment.get(
            "voyage_no"
        )

        segments_count = int(
            raw.get(
                "segments_count",
                len(raw_segments) or 1,
            )
        )

        transfers = max(
            0,
            segments_count - 1,
        )

        review_summary = raw.get(
            "review_summary"
        )

        rating: float | None = None
        review_count: int | None = None

        if isinstance(
            review_summary,
            dict,
        ):
            raw_rating = review_summary.get(
                "rating"
            )

            raw_review_count = (
                review_summary.get(
                    "review_count"
                )
            )

            if raw_rating is not None:
                rating = float(
                    raw_rating
                )

            if raw_review_count is not None:
                review_count = int(
                    raw_review_count
                )

        return TransportSegment(
            id=str(offer_id),
            mode=mode,
            origin=origin,
            destination=destination,
            departure=departure,
            arrival=arrival,
            price=party_price,
            source_price=source_price,
            currency=currency,
            duration_minutes=int(
                raw.get(
                    "duration_min",
                    0,
                )
            ),
            transfers=transfers,
            carrier=carrier,
            voyage_no=(
                str(voyage_no)
                if voyage_no is not None
                else None
            ),
            booking_url=(
                raw.get("checkout_url")
                or raw.get(
                    "search_results_url"
                )
            ),
            search_results_url=raw.get(
                "search_results_url"
            ),
            checkout_ref=raw.get(
                "checkout_ref"
            ),
            details_ref=raw.get(
                "details_ref"
            ),
            rating=rating,
            review_count=review_count,
        )

    @staticmethod
    def _extract_carrier(
        raw: dict[str, Any],
        first_segment: dict[str, Any],
    ) -> str | None:

        carriers = raw.get(
            "carriers"
        )

        if (
            isinstance(carriers, list)
            and carriers
        ):
            return str(
                carriers[0]
            )

        segment_carrier = (
            first_segment.get(
                "carrier"
            )
        )

        if segment_carrier is None:
            return None

        return str(segment_carrier)

    @staticmethod
    def _normalize_party_price(
        *,
        mode: TransportMode,
        source_price: float,
        travelers: int,
    ) -> int:
        """
        Produce one comparable party-level RUB amount.

        Bus:
        Tutu explicitly returns whole-party prices.

        Avia:
        Search receives passenger composition and
        offer price is treated as group price.

        Railway:
        Search price represents the selected adult
        fare. For our adults-only MVP we scale it
        by traveler count.

        Etrain:
        search_etrain has no passenger-count
        argument, therefore scale by traveler count.

        Before the pitch we should verify the rail
        assumption against one actual checkout.
        """

        if mode in {
            TransportMode.TRAIN,
            TransportMode.SUBURBAN_TRAIN,
        }:
            normalized = (
                source_price
                * travelers
            )
        else:
            normalized = source_price

        return int(
            math.ceil(normalized)
        )