from __future__ import annotations

from datetime import date
from typing import Any
from urllib.parse import urlparse
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.booking_schemas import (
    BookingResponse,
    BookingStep,
    BookingStepOption,
    CreateBookingRequest,
    SubmitBookingStepRequest,
)
from app.models import BookingRecord, ConversationRecord, utc_now
from app.schemas import SearchOption, TravelService, TripDetails


class BookingNotFoundError(Exception):
    pass


class BookingValidationError(ValueError):
    pass


PRODUCT_STEPS: dict[TravelService, list[BookingStep]] = {
    TravelService.TRAIN: [
        BookingStep.SELECT_CARRIAGE,
        BookingStep.SELECT_SEATS,
        BookingStep.CONFIRM_FARE,
        BookingStep.PASSENGERS,
        BookingStep.CONFIRM,
        BookingStep.CHECKOUT,
    ],
    TravelService.FLIGHT: [
        BookingStep.SELECT_FARE,
        BookingStep.SELECT_EXTRAS,
        BookingStep.DOCUMENTS,
        BookingStep.CONFIRM,
        BookingStep.CHECKOUT,
    ],
    TravelService.BUS: [
        BookingStep.SELECT_SEATS,
        BookingStep.CONFIRM_FARE,
        BookingStep.PASSENGERS,
        BookingStep.CONFIRM,
        BookingStep.CHECKOUT,
    ],
    TravelService.HOTEL: [
        BookingStep.SELECT_ROOM,
        BookingStep.CONFIRM_FARE,
        BookingStep.GUESTS,
        BookingStep.CONFIRM,
        BookingStep.CHECKOUT,
    ],
}


class BookingService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, request: CreateBookingRequest) -> BookingResponse:
        conversation = await self._session.get(ConversationRecord, request.session_id)
        if conversation is None or conversation.user_id != request.user_id:
            raise BookingNotFoundError
        trip = TripDetails.model_validate(conversation.trip)
        if trip.service_type is None or trip.passengers is None:
            raise BookingValidationError("Параметры поездки ещё не собраны.")
        self._validate_option_type(request.option, trip.service_type)

        record = BookingRecord(
            id=uuid4(),
            user_id=request.user_id,
            conversation_id=request.session_id,
            product_type=trip.service_type.value,
            option=request.option.model_dump(mode="json"),
            steps=[step.value for step in PRODUCT_STEPS[trip.service_type]],
            current_step_index=0,
            selections={},
            travelers_count=trip.passengers,
        )
        self._session.add(record)
        await self._session.commit()
        return self._response(record)

    async def get(self, booking_id: UUID, user_id: UUID) -> BookingResponse:
        return self._response(await self._load(booking_id, user_id))

    async def submit(
        self,
        booking_id: UUID,
        request: SubmitBookingStepRequest,
    ) -> BookingResponse:
        record = await self._load(booking_id, request.user_id)
        current_step = self._current_step(record)
        if request.step is not current_step:
            raise BookingValidationError(
                f"Ожидается шаг {current_step.value}, получен {request.step.value}."
            )
        normalized = self._validate_step(record, current_step, request.data)
        selections = dict(record.selections)
        selections[current_step.value] = normalized
        record.selections = selections
        record.updated_at = utc_now()

        if current_step is BookingStep.CONFIRM:
            record.confirmed = True
        if current_step is not BookingStep.CHECKOUT:
            record.current_step_index += 1
        else:
            if not record.confirmed:
                raise BookingValidationError("Сначала подтвердите оформление.")
            record.checkout_url = self._checkout_url(SearchOption.model_validate(record.option))

        await self._session.commit()
        return self._response(record)

    async def _load(self, booking_id: UUID, user_id: UUID) -> BookingRecord:
        record = await self._session.get(BookingRecord, booking_id)
        if record is None or record.user_id != user_id:
            await self._session.rollback()
            raise BookingNotFoundError
        return record

    @staticmethod
    def _validate_option_type(option: SearchOption, product_type: TravelService) -> None:
        if product_type is TravelService.HOTEL:
            if option.hotel is None:
                raise BookingValidationError("Для оформления нужен выбранный отель.")
            return
        if option.outbound is None or option.outbound.mode != product_type.value:
            raise BookingValidationError("Выбранный вариант не соответствует типу поездки.")

    @staticmethod
    def sanitize_assistance(
        booking: BookingResponse,
        proposed_data: dict[str, Any],
    ) -> dict[str, Any]:
        step = booking.current_step
        available = {option.id for option in booking.current_options if option.available}
        if step in {
            BookingStep.SELECT_CARRIAGE,
            BookingStep.SELECT_ROOM,
            BookingStep.SELECT_FARE,
        }:
            option_id = proposed_data.get("option_id")
            return {"option_id": option_id} if option_id in available else {}
        if step is BookingStep.SELECT_EXTRAS:
            option_ids = proposed_data.get("option_ids")
            if not isinstance(option_ids, list):
                return {}
            return {
                "option_ids": list(
                    dict.fromkeys(item for item in option_ids if item in available)
                )
            }
        if step is BookingStep.SELECT_SEATS:
            seat_ids = proposed_data.get("seat_ids")
            if not isinstance(seat_ids, list):
                return {}
            seats = list(dict.fromkeys(item for item in seat_ids if item in available))
            return {"seat_ids": seats} if len(seats) == booking.travelers_count else {}
        if step in {BookingStep.PASSENGERS, BookingStep.DOCUMENTS, BookingStep.GUESTS}:
            travelers = proposed_data.get("travelers")
            if not isinstance(travelers, list):
                return {}
            allowed_fields = {"full_name"}
            if step is not BookingStep.GUESTS:
                allowed_fields.update({"birth_date", "document_type", "document_number"})
            sanitized = []
            for traveler in travelers[: booking.travelers_count]:
                if not isinstance(traveler, dict):
                    continue
                sanitized.append(
                    {
                        key: str(value).strip()[:200]
                        for key, value in traveler.items()
                        if key in allowed_fields and value is not None
                    }
                )
            return {"travelers": sanitized} if any(sanitized) else {}
        return {}

    def _validate_step(
        self,
        record: BookingRecord,
        step: BookingStep,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        options = self._options(record, step)
        if step in {
            BookingStep.SELECT_CARRIAGE,
            BookingStep.SELECT_ROOM,
            BookingStep.SELECT_FARE,
        }:
            return {"option_id": self._allowed_option(data, options)}
        if step is BookingStep.SELECT_EXTRAS:
            selected = data.get("option_ids", [])
            if not isinstance(selected, list):
                raise BookingValidationError("Дополнительные услуги переданы неверно.")
            allowed = {option.id for option in options if option.available}
            if any(item not in allowed for item in selected):
                raise BookingValidationError("Выбрана недоступная услуга.")
            return {"option_ids": list(dict.fromkeys(selected))}
        if step is BookingStep.SELECT_SEATS:
            seat_ids = data.get("seat_ids")
            if not isinstance(seat_ids, list) or len(seat_ids) != record.travelers_count:
                raise BookingValidationError(
                    f"Выберите {record.travelers_count} мест(а) по числу путешественников."
                )
            allowed = {option.id for option in options if option.available}
            if len(set(seat_ids)) != len(seat_ids) or any(seat not in allowed for seat in seat_ids):
                raise BookingValidationError("Выбраны повторяющиеся или недоступные места.")
            return {"seat_ids": seat_ids}
        if step is BookingStep.CONFIRM_FARE:
            if data.get("accepted") is not True:
                raise BookingValidationError("Подтвердите условия тарифа.")
            return {"accepted": True}
        if step in {BookingStep.PASSENGERS, BookingStep.DOCUMENTS, BookingStep.GUESTS}:
            travelers = data.get("travelers")
            if not isinstance(travelers, list) or len(travelers) != record.travelers_count:
                raise BookingValidationError("Заполните данные всех путешественников.")
            return {"travelers": [self._validate_traveler(item, step) for item in travelers]}
        if step is BookingStep.CONFIRM:
            if data.get("approved") is not True:
                raise BookingValidationError("Требуется явное подтверждение пользователя.")
            return {"approved": True}
        if step is BookingStep.CHECKOUT:
            return {}
        raise BookingValidationError("Неизвестный шаг оформления.")

    @staticmethod
    def _allowed_option(data: dict[str, Any], options: list[BookingStepOption]) -> str:
        option_id = data.get("option_id")
        if not isinstance(option_id, str) or option_id not in {
            option.id for option in options if option.available
        }:
            raise BookingValidationError("Выберите доступный вариант.")
        return option_id

    @staticmethod
    def _validate_traveler(item: Any, step: BookingStep) -> dict[str, str]:
        if not isinstance(item, dict):
            raise BookingValidationError("Данные путешественника переданы неверно.")
        full_name = " ".join(str(item.get("full_name", "")).split())
        if len(full_name) < 3:
            raise BookingValidationError("Укажите имя и фамилию путешественника.")
        result = {"full_name": full_name}
        if step is BookingStep.GUESTS:
            return result
        birth_date = str(item.get("birth_date", ""))
        try:
            parsed_birth_date = date.fromisoformat(birth_date)
        except ValueError as exc:
            raise BookingValidationError("Укажите корректную дату рождения.") from exc
        if parsed_birth_date >= date.today():
            raise BookingValidationError("Дата рождения должна быть в прошлом.")
        result["birth_date"] = birth_date
        document_number = "".join(str(item.get("document_number", "")).split())
        if len(document_number) < 4:
            raise BookingValidationError("Укажите номер документа.")
        result["document_number"] = document_number
        result["document_type"] = str(item.get("document_type", "domestic_passport"))
        return result

    def _response(self, record: BookingRecord) -> BookingResponse:
        steps = [BookingStep(step) for step in record.steps]
        current = self._current_step(record)
        return BookingResponse(
            id=record.id,
            user_id=record.user_id,
            session_id=record.conversation_id,
            product_type=TravelService(record.product_type),
            option=SearchOption.model_validate(record.option),
            steps=steps,
            current_step=current,
            completed_steps=steps[: record.current_step_index],
            selections=record.selections,
            travelers_count=record.travelers_count,
            current_options=self._options(record, current),
            checkout_url=record.checkout_url,
        )

    @staticmethod
    def _current_step(record: BookingRecord) -> BookingStep:
        index = min(record.current_step_index, len(record.steps) - 1)
        return BookingStep(record.steps[index])

    @staticmethod
    def _options(record: BookingRecord, step: BookingStep) -> list[BookingStepOption]:
        if step is BookingStep.SELECT_CARRIAGE:
            return [
                BookingStepOption(id="seated", title="Сидячий", description="Базовый тариф"),
                BookingStepOption(
                    id="reserved", title="Плацкарт", description="Спальное место", price_delta=900
                ),
                BookingStepOption(
                    id="compartment", title="Купе", description="4 места в купе", price_delta=2700
                ),
                BookingStepOption(
                    id="lux", title="СВ", description="2 места в купе", price_delta=8500
                ),
            ]
        if step is BookingStep.SELECT_ROOM:
            hotel = SearchOption.model_validate(record.option).hotel
            return [
                BookingStepOption(
                    id="recommended-room",
                    title=hotel.name if hotel else "Рекомендуемый номер",
                    description="Номер из найденного предложения",
                )
            ]
        if step is BookingStep.SELECT_FARE:
            return [
                BookingStepOption(id="basic", title="Эконом", description="Ручная кладь"),
                BookingStepOption(
                    id="optimal", title="Оптимум", description="Багаж и обмен", price_delta=3500
                ),
                BookingStepOption(
                    id="flex", title="Гибкий", description="Возврат и выбор места", price_delta=7000
                ),
            ]
        if step is BookingStep.SELECT_EXTRAS:
            return [
                BookingStepOption(
                    id="baggage",
                    title="Багаж 23 кг",
                    description="Одна единица багажа",
                    price_delta=2500,
                ),
                BookingStepOption(
                    id="meal",
                    title="Питание",
                    description="Горячее питание на борту",
                    price_delta=900,
                ),
                BookingStepOption(
                    id="insurance",
                    title="Страховка",
                    description="На период поездки",
                    price_delta=650,
                ),
            ]
        if step is BookingStep.SELECT_SEATS:
            return [
                BookingStepOption(
                    id=str(number),
                    title=f"Место {number}",
                    description="Предварительный выбор",
                    available=number not in {3, 7, 12, 18},
                )
                for number in range(1, 25)
            ]
        return []

    @staticmethod
    def _checkout_url(option: SearchOption) -> str:
        candidate = option.action_url or ""
        parsed = urlparse(candidate)
        hostname = (parsed.hostname or "").lower()
        if parsed.scheme == "https" and (hostname == "tutu.ru" or hostname.endswith(".tutu.ru")):
            return candidate
        if option.hotel:
            return "https://hotel.tutu.ru/"
        mode = option.outbound.mode if option.outbound else ""
        return {
            "train": "https://www.tutu.ru/poezda/",
            "flight": "https://avia.tutu.ru/",
            "bus": "https://bus.tutu.ru/",
        }.get(mode, "https://www.tutu.ru/")
