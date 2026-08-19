from itertools import product
from statistics import mean

from app.schemas import (
    BestTrip,
    PriceSummary,
    Recommendation,
    RecommendationStatus,
    TripCandidates,
    TripIntent,
    TripSnapshot,
)


class NoMatchingTripsError(RuntimeError):
    pass


def select_best_trip(candidates: TripCandidates, intent: TripIntent) -> BestTrip:
    if not candidates.hotels:
        return _select_transport_only(candidates, intent)

    combinations: list[dict[str, object]] = []
    for transport, hotel in product(candidates.transport[:5], candidates.hotels[:5]):
        if intent.direct_only and transport.transfers:
            continue
        if hotel.rating < intent.hotel_rating_min:
            continue
        useful_time = (transport.return_departure_at - transport.arrival_at).total_seconds() / 3600
        if useful_time <= 0:
            continue
        combinations.append(
            {
                "transport": transport,
                "hotel": hotel,
                "total_price": transport.price + hotel.price_total,
                "useful_time": useful_time,
            }
        )

    if not combinations:
        raise NoMatchingTripsError("No complete trip combinations were found.")

    prices = [int(item["total_price"]) for item in combinations]
    if intent.budget is not None:
        affordable = [item for item in combinations if int(item["total_price"]) <= intent.budget]
        if affordable:
            combinations = affordable

    useful_times = [float(item["useful_time"]) for item in combinations]
    min_price, max_price = min(prices), max(prices)
    min_time, max_time = min(useful_times), max(useful_times)

    ranked: list[BestTrip] = []
    for item in combinations:
        transport = item["transport"]
        hotel = item["hotel"]
        total_price = int(item["total_price"])
        useful_time = float(item["useful_time"])
        price_score = _inverse_scale(total_price, min_price, max_price)
        useful_time_score = _scale(useful_time, min_time, max_time)
        direct_score = 1.0 if transport.transfers == 0 else 0.0
        score = (
            price_score * 0.50
            + useful_time_score * 0.20
            + (hotel.rating / 10) * 0.20
            + direct_score * 0.10
        )
        ranked.append(
            BestTrip(
                total_price=total_price,
                transport_price=transport.price,
                hotel_price=hotel.price_total,
                trip_score=round(score * 100, 1),
                useful_time_hours=round(useful_time, 1),
                transfers=transport.transfers,
                hotel_rating=hotel.rating,
                transport=transport,
                hotel=hotel,
            )
        )

    return max(ranked, key=lambda trip: (trip.trip_score, -trip.total_price))


def _select_transport_only(candidates: TripCandidates, intent: TripIntent) -> BestTrip:
    offers = [
        transport
        for transport in candidates.transport[:5]
        if not (intent.direct_only and transport.transfers)
    ]
    if intent.budget is not None:
        affordable = [transport for transport in offers if transport.price <= intent.budget]
        if affordable:
            offers = affordable
    if not offers:
        raise NoMatchingTripsError("No matching transport options were found.")

    min_price = min(transport.price for transport in offers)
    max_price = max(transport.price for transport in offers)
    ranked = [
        BestTrip(
            total_price=transport.price,
            transport_price=transport.price,
            hotel_price=0,
            trip_score=round(
                (
                    _inverse_scale(transport.price, min_price, max_price) * 0.8
                    + (1.0 if transport.transfers == 0 else 0.0) * 0.2
                )
                * 100,
                1,
            ),
            useful_time_hours=round(transport.duration_minutes / 60, 1),
            transfers=transport.transfers,
            hotel_rating=0,
            transport=transport,
            hotel=None,
        )
        for transport in offers
    ]
    return max(ranked, key=lambda trip: (trip.trip_score, -trip.total_price))


def summarize_prices(snapshots: list[TripSnapshot]) -> PriceSummary:
    prices = [snapshot.best_trip.total_price for snapshot in snapshots]
    current = prices[-1]
    minimum = min(prices)
    return PriceSummary(
        current_price=current,
        minimum_price=minimum,
        average_price=round(mean(prices)),
        difference_from_min=current - minimum,
    )


def recommend(snapshots: list[TripSnapshot]) -> Recommendation:
    if len(snapshots) < 2:
        return Recommendation(
            status=RecommendationStatus.COLLECTING_DATA,
            message="Нужно ещё одно наблюдение, чтобы сравнить цену.",
        )

    summary = summarize_prices(snapshots)
    current = summary.current_price
    if current <= summary.minimum_price * 1.03:
        return Recommendation(
            status=RecommendationStatus.BUY_NOW,
            message="Цена находится рядом с наблюдаемым минимумом.",
        )
    if current > summary.minimum_price * 1.10:
        return Recommendation(
            status=RecommendationStatus.WAIT,
            message="Цена заметно выше недавнего минимума — можно подождать.",
        )
    return Recommendation(
        status=RecommendationStatus.GOOD_VALUE,
        message="Цена выглядит разумно относительно накопленной истории.",
    )


def _scale(value: float, minimum: float, maximum: float) -> float:
    if maximum == minimum:
        return 1.0
    return (value - minimum) / (maximum - minimum)


def _inverse_scale(value: float, minimum: float, maximum: float) -> float:
    return 1 - _scale(value, minimum, maximum)
