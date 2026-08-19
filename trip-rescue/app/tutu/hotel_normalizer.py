from __future__ import annotations

import math
from datetime import date
from typing import Any

from app.models.journey import HotelOption


class TutuHotelNormalizationError(
    ValueError
):
    pass


class TutuHotelNormalizer:
    def normalize_search_result(
        self,
        payload: dict[str, Any],
    ) -> list[HotelOption]:

        raw_hotels = payload.get(
            "hotels",
            [],
        )

        if not isinstance(
            raw_hotels,
            list,
        ):
            raise TutuHotelNormalizationError(
                "Tutu hotels payload "
                "'hotels' is not a list"
            )

        stay = payload.get(
            "stay",
            {},
        )

        check_in: date | None = None
        check_out: date | None = None
        nights: int | None = None

        if isinstance(stay, dict):
            check_in_raw = stay.get(
                "check_in"
            )

            check_out_raw = stay.get(
                "check_out"
            )

            nights_raw = stay.get(
                "nights"
            )

            if check_in_raw:
                check_in = (
                    date.fromisoformat(
                        str(check_in_raw)
                    )
                )

            if check_out_raw:
                check_out = (
                    date.fromisoformat(
                        str(check_out_raw)
                    )
                )

            if nights_raw is not None:
                nights = int(
                    nights_raw
                )

        result: list[HotelOption] = []

        for raw in raw_hotels:
            if not isinstance(
                raw,
                dict,
            ):
                continue

            try:
                hotel = self.normalize_hotel(
                    raw=raw,
                    check_in=check_in,
                    check_out=check_out,
                    nights=nights,
                )
            except (
                KeyError,
                TypeError,
                ValueError,
                TutuHotelNormalizationError,
            ):
                continue

            result.append(
                hotel
            )

        result.sort(
            key=lambda hotel: (
                hotel.price,
                -(
                    hotel.rating
                    if hotel.rating
                    is not None
                    else 0
                ),
                -(
                    hotel.review_count
                    if hotel.review_count
                    is not None
                    else 0
                ),
            )
        )

        return result

    def normalize_hotel(
        self,
        *,
        raw: dict[str, Any],
        check_in: date | None,
        check_out: date | None,
        nights: int | None,
    ) -> HotelOption:

        hotel_id = (
            raw.get("hotel_id")
            or raw.get("hotel_geo_id")
        )

        if not hotel_id:
            raise TutuHotelNormalizationError(
                "Hotel has no id"
            )

        name = raw.get("name")

        if not name:
            raise TutuHotelNormalizationError(
                "Hotel has no name"
            )

        best_offer = raw.get(
            "best_offer"
        )

        if not isinstance(
            best_offer,
            dict,
        ):
            raise TutuHotelNormalizationError(
                "Hotel has no best_offer"
            )

        price_data = best_offer.get(
            "price"
        )

        if not isinstance(
            price_data,
            dict,
        ):
            raise TutuHotelNormalizationError(
                "Hotel has no price"
            )

        amount = float(
            price_data["amount"]
        )

        currency = str(
            price_data.get(
                "currency",
                "RUB",
            )
        )

        # IMPORTANT:
        # Tutu returns whole-stay total here.
        # NEVER multiply this by nights.
        price = int(
            math.ceil(amount)
        )

        photos = raw.get(
            "photos",
            [],
        )

        photo_url: str | None = None

        if (
            isinstance(photos, list)
            and photos
        ):
            photo_url = str(
                photos[0]
            )

        rating_raw = raw.get(
            "rating"
        )

        review_count_raw = raw.get(
            "review_count"
        )

        stars_raw = raw.get(
            "stars"
        )

        room_size_raw = (
            best_offer.get(
                "room_size_sqm"
            )
        )

        return HotelOption(
            id=str(hotel_id),
            name=str(name),
            price=price,
            source_price=amount,
            currency=currency,
            stars=(
                int(stars_raw)
                if stars_raw is not None
                else None
            ),
            rating=(
                float(rating_raw)
                if rating_raw is not None
                else None
            ),
            review_count=(
                int(review_count_raw)
                if review_count_raw
                is not None
                else None
            ),
            address=(
                str(raw["address"])
                if raw.get("address")
                is not None
                else None
            ),
            room_name=(
                str(
                    best_offer[
                        "room_name"
                    ]
                )
                if best_offer.get(
                    "room_name"
                )
                is not None
                else None
            ),
            room_size_sqm=(
                float(room_size_raw)
                if room_size_raw
                is not None
                else None
            ),
            check_in=check_in,
            check_out=check_out,
            nights=nights,
            breakfast_included=(
                best_offer.get(
                    "breakfast_included"
                )
            ),
            meal_name=(
                str(
                    best_offer[
                        "meal_name"
                    ]
                )
                if best_offer.get(
                    "meal_name"
                )
                is not None
                else None
            ),
            free_cancellation=(
                best_offer.get(
                    "free_cancellation"
                )
            ),
            booking_url=(
                best_offer.get(
                    "checkout_url"
                )
                or raw.get(
                    "checkout_url"
                )
            ),
            checkout_ref=raw.get(
                "checkout_ref"
            ),
            offerpack_hash=(
                str(
                    best_offer[
                        "offerpack_hash"
                    ]
                )
                if best_offer.get(
                    "offerpack_hash"
                )
                is not None
                else None
            ),
            photo_url=photo_url,
        )