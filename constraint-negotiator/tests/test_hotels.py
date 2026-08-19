from datetime import date

from app.tutu.hotel_normalizer import (
    TutuHotelNormalizer,
)


def test_hotel_price_is_whole_stay_total() -> None:
    payload = {
        "hotels": [
            {
                "hotel_id": "hotel-1",
                "name": "Test Hotel",
                "stars": 3,
                "rating": 8.5,
                "review_count": 100,
                "address": "1 км от центра",
                "photos": [
                    "https://example.com/hotel.jpg"
                ],
                "best_offer": {
                    "offerpack_hash": "pack-1",
                    "room_name": "Standard",
                    "price": {
                        "amount": 6550.0,
                        "currency": "RUB",
                    },
                    "price_basis": "stay_total",
                    "checkout_url": (
                        "https://example.com/checkout"
                    ),
                    "breakfast_included": False,
                    "meal_name": None,
                    "free_cancellation": True,
                    "room_size_sqm": 20.0,
                },
                "checkout_ref": {
                    "transport": "hotels",
                    "hotel_geo_id": "hotel-1",
                },
            }
        ],
        "stay": {
            "check_in": "2026-08-21",
            "check_out": "2026-08-23",
            "nights": 2,
        },
    }

    normalizer = (
        TutuHotelNormalizer()
    )

    hotels = (
        normalizer
        .normalize_search_result(
            payload
        )
    )

    assert len(hotels) == 1

    hotel = hotels[0]

    # This MUST remain 6550.
    # It must NOT become 13100.
    assert hotel.price == 6550

    assert hotel.nights == 2

    assert (
        hotel.check_in
        == date(2026, 8, 21)
    )

    assert (
        hotel.check_out
        == date(2026, 8, 23)
    )


def test_hotels_are_sorted_by_price() -> None:
    payload = {
        "hotels": [
            {
                "hotel_id": "expensive",
                "name": "Expensive",
                "rating": 9.0,
                "best_offer": {
                    "price": {
                        "amount": 12000,
                        "currency": "RUB",
                    },
                },
            },
            {
                "hotel_id": "cheap",
                "name": "Cheap",
                "rating": 7.5,
                "best_offer": {
                    "price": {
                        "amount": 4000,
                        "currency": "RUB",
                    },
                },
            },
        ],
        "stay": {
            "check_in": "2026-08-22",
            "check_out": "2026-08-23",
            "nights": 1,
        },
    }

    normalizer = (
        TutuHotelNormalizer()
    )

    hotels = (
        normalizer
        .normalize_search_result(
            payload
        )
    )

    assert len(hotels) == 2

    assert (
        hotels[0].id
        == "cheap"
    )

    assert (
        hotels[0].price
        == 4000
    )


def test_hotel_checkout_data_is_preserved() -> None:
    payload = {
        "hotels": [
            {
                "hotel_id": "hotel-1",
                "name": "Hotel",
                "best_offer": {
                    "offerpack_hash": "abc123",
                    "price": {
                        "amount": 5000,
                        "currency": "RUB",
                    },
                    "checkout_url": (
                        "https://example.com/hotel"
                    ),
                },
                "checkout_ref": {
                    "transport": "hotels",
                    "hotel_geo_id": "hotel-1",
                    "check_in": "2026-08-22",
                    "check_out": "2026-08-23",
                    "adults": 2,
                },
            }
        ],
        "stay": {
            "check_in": "2026-08-22",
            "check_out": "2026-08-23",
            "nights": 1,
        },
    }

    normalizer = (
        TutuHotelNormalizer()
    )

    hotel = (
        normalizer
        .normalize_search_result(
            payload
        )[0]
    )

    assert (
        hotel.offerpack_hash
        == "abc123"
    )

    assert (
        hotel.checkout_ref[
            "transport"
        ]
        == "hotels"
    )

    assert (
        hotel.booking_url
        == "https://example.com/hotel"
    )