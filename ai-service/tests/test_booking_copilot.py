from typing import Any

import pytest

from app.booking.graph import build_booking_copilot
from app.domain.booking import (
    BookingCopilotDecision,
    BookingCopilotRequest,
    BookingOption,
    BookingProductType,
    BookingStep,
    BookingTravelerDraft,
)
from app.domain.travel import TravelService, TripDetails


class FakeCopilotModel:
    def __init__(self, decision: BookingCopilotDecision) -> None:
        self.decision = decision

    async def ainvoke(self, _: list[dict[str, Any]]) -> BookingCopilotDecision:
        return self.decision


def request_for(step: BookingStep) -> BookingCopilotRequest:
    return BookingCopilotRequest(
        product_type=BookingProductType.FLIGHT,
        current_step=step,
        travelers_count=1,
        current_options=[
            BookingOption(id="basic", title="Эконом", description="Ручная кладь"),
            BookingOption(id="flex", title="Гибкий", description="Возврат"),
        ],
        trip=TripDetails(service_type=TravelService.FLIGHT),
    )


@pytest.mark.asyncio
async def test_copilot_keeps_only_available_option() -> None:
    workflow = build_booking_copilot(
        FakeCopilotModel(
            BookingCopilotDecision(
                assistant_message="Рекомендую базовый тариф.",
                option_id="basic",
            )
        )
    )
    result = await workflow.ainvoke({"request": request_for(BookingStep.SELECT_FARE)})
    assert result["response"].proposed_data == {"option_id": "basic"}
    assert result["response"].can_apply is True
    assert result["response"].requires_user_confirmation is True


@pytest.mark.asyncio
async def test_copilot_does_not_approve_checkout() -> None:
    workflow = build_booking_copilot(
        FakeCopilotModel(
            BookingCopilotDecision(
                assistant_message="Проверьте заказ перед подтверждением.",
                option_id="basic",
            )
        )
    )
    result = await workflow.ainvoke({"request": request_for(BookingStep.CONFIRM)})
    assert result["response"].proposed_data == {}
    assert result["response"].can_apply is False


@pytest.mark.asyncio
async def test_copilot_returns_partial_passenger_draft_without_inventing_fields() -> None:
    workflow = build_booking_copilot(
        FakeCopilotModel(
            BookingCopilotDecision(
                assistant_message="Нашёл имя, но не хватает документа.",
                travelers=[BookingTravelerDraft(full_name="Иван Иванов")],
                missing_fields=["document_number"],
            )
        )
    )
    result = await workflow.ainvoke({"request": request_for(BookingStep.DOCUMENTS)})
    assert result["response"].proposed_data == {
        "travelers": [{"full_name": "Иван Иванов"}]
    }
    assert result["response"].missing_fields == ["document_number"]


@pytest.mark.asyncio
async def test_copilot_normalizes_localized_birth_date_for_html_form() -> None:
    workflow = build_booking_copilot(
        FakeCopilotModel(
            BookingCopilotDecision(
                assistant_message="Заполнил данные пассажира.",
                travelers=[
                    BookingTravelerDraft(
                        full_name="Иван Иванов",
                        birth_date="02.01.1990",
                        document_type="domestic_passport",
                        document_number="4510123456",
                    )
                ],
            )
        )
    )
    result = await workflow.ainvoke({"request": request_for(BookingStep.DOCUMENTS)})
    assert result["response"].proposed_data["travelers"][0]["birth_date"] == "1990-01-02"


@pytest.mark.asyncio
async def test_copilot_recovers_explicit_extra_by_exact_available_title() -> None:
    request = request_for(BookingStep.SELECT_EXTRAS)
    request.current_options = [
        BookingOption(id="baggage", title="Багаж 23 кг", description="Одна единица"),
        BookingOption(id="meal", title="Питание", description="Горячее питание"),
    ]
    request.instruction = "Добавь только багаж 23 кг, питание не нужно"
    workflow = build_booking_copilot(
        FakeCopilotModel(
            BookingCopilotDecision(
                assistant_message="Добавлю только багаж.",
                option_ids=[],
            )
        )
    )
    result = await workflow.ainvoke({"request": request})
    assert result["response"].proposed_data == {"option_ids": ["baggage"]}
