from app.agent.search_options import build_search_options


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
