from app.agent.search_options import build_search_options


def test_accepts_direct_hotel_product_options() -> None:
    options = build_search_options(
        {
            "status": "success",
            "options": [
                {
                    "id": "hotel-1",
                    "kind": "journey",
                    "title": "Отель у Кремля",
                    "total_price": 8000,
                    "currency": "RUB",
                    "hotel": {
                        "name": "Отель у Кремля",
                        "price": 8000,
                        "currency": "RUB",
                        "nights": 2,
                    },
                    "action_url": "https://hotel.tutu.ru/offers/details?id=1",
                }
            ],
        },
        None,
    )

    assert options[0].outbound is None
    assert options[0].hotel is not None
    assert options[0].hotel.nights == 2


def test_builds_tracking_payload_for_direct_transport_option() -> None:
    options = build_search_options(
        {
            "status": "success",
            "trip_spec": {
                "origin": "Санкт-Петербург",
                "destination": "Москва",
                "outbound_date": "2026-09-10",
                "return_date": None,
                "travelers": 1,
                "budget": 30_000,
                "max_transfers": None,
            },
            "options": [
                {
                    "id": "train-745y",
                    "kind": "journey",
                    "title": "Санкт-Петербург — Москва",
                    "total_price": 1141,
                    "currency": "RUB",
                    "outbound": {
                        "mode": "train",
                        "origin": "Санкт-Петербург",
                        "destination": "Москва",
                        "departure": "2026-09-10T16:07:00+03:00",
                        "arrival": "2026-09-10T22:58:00+03:00",
                        "price": 1141,
                        "duration_minutes": 411,
                        "transfers": 0,
                        "carrier": "ФПК",
                    },
                    "action_url": "https://www.tutu.ru/poezda/",
                }
            ],
        },
        None,
    )

    payload = options[0].tracking_payload
    assert payload is not None
    assert payload.trip_spec.return_date is None
    assert payload.journeys[0].inbound is None
    assert payload.journeys[0].outbound.mode == "train"


def test_builds_clickable_card_data_from_mcp_journey() -> None:
    options = build_search_options(
        {
            "status": "success",
            "trip_spec": {"origin": "Москва", "destination": "Казань"},
            "journeys": [
                {
                    "id": "journey-1",
                    "total_price": 18_900,
                    "outbound": {
                        "mode": "train",
                        "origin": "Москва",
                        "destination": "Казань",
                        "departure": "2026-09-01T10:00:00+03:00",
                        "arrival": "2026-09-01T21:30:00+03:00",
                        "price": 9_500,
                        "currency": "RUB",
                        "transfers": 0,
                        "carrier": "ФПК",
                        "voyage_no": "002Э",
                        "booking_url": "https://www.tutu.ru/poezda/view_d.php?np=002E",
                    },
                    "inbound": {
                        "mode": "train",
                        "origin": "Казань",
                        "destination": "Москва",
                        "departure": "2026-09-05T18:00:00+03:00",
                        "arrival": "2026-09-06T05:30:00+03:00",
                        "price": 9_400,
                        "currency": "RUB",
                        "transfers": 0,
                    },
                }
            ],
            "alternatives": [],
        },
        "/search/train?origin=Москва",
    )

    assert len(options) == 1
    assert options[0].kind == "journey"
    assert options[0].title == "Москва — Казань"
    assert options[0].total_price == 18_900
    assert options[0].action_url.startswith("https://www.tutu.ru/")
    assert options[0].tracking_payload is not None
    assert options[0].tracking_payload.trip_spec.outbound_date == "2026-09-01"
    assert options[0].tracking_payload.journeys[0].transport_price == 18_900


def test_builds_relaxation_card_and_uses_redirect_fallback() -> None:
    journey = {
        "id": "journey-flex",
        "total_price": 24_000,
        "outbound": {
            "mode": "flight",
            "origin": "Москва",
            "destination": "Стамбул",
            "departure": "2026-09-01T08:00:00+03:00",
            "arrival": "2026-09-01T12:00:00+03:00",
            "price": 12_000,
        },
        "inbound": {
            "mode": "flight",
            "origin": "Стамбул",
            "destination": "Москва",
            "departure": "2026-09-08T16:00:00+03:00",
            "arrival": "2026-09-08T20:00:00+03:00",
            "price": 12_000,
        },
    }
    options = build_search_options(
        {
            "status": "negotiation_required",
            "journeys": [],
            "alternatives": [
                {
                    "id": "relaxation-1",
                    "summary": {
                        "headline": "Чуть выше бюджета",
                        "explanation": "Доплата 4 000 ₽ сохраняет удобное время.",
                    },
                    "changes": [{"title": "Бюджет до 24 000 ₽"}],
                    "journey": journey,
                }
            ],
        },
        "/search/flight?origin=Москва",
    )

    assert options[0].kind == "relaxation"
    assert options[0].title == "Чуть выше бюджета"
    assert options[0].changes == ["Бюджет до 24 000 ₽"]
    assert options[0].action_url == "/search/flight?origin=Москва"
