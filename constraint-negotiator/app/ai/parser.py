from datetime import date

from langchain_openai import ChatOpenAI

from app.config import get_settings
from app.models.trip import TripSpec


class TripParser:
    def __init__(self) -> None:
        settings = get_settings()

        if settings.openai_api_key is None:
            self._llm = None
            return

        self._llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key.get_secret_value(),
            temperature=0,
        ).with_structured_output(
            TripSpec,
            method="json_schema",
        )

    async def parse(
        self,
        message: str,
        reference_date: date,
    ) -> TripSpec:

        if self._llm is None:
            raise RuntimeError(
                "OPENAI_API_KEY is not configured"
            )

        prompt = f"""
Ты преобразуешь естественный запрос путешественника
в структурированный TripSpec.

Текущая дата:
{reference_date.isoformat()}

Правила:

1. Не добавляй ограничения, которых пользователь не задавал.
2. Фразы вроде "обязательно", "ни в коем случае",
   "точно не", "должен" означают hard constraint.
3. "Не люблю", "желательно", "предпочитаю" —
   это предпочтение, а не hard constraint.
4. budget — общий бюджет поездки.
5. Время должно быть в локальном времени поездки.
6. Если пользователь говорит "на выходные",
   выбери ближайшие логичные выходные
   относительно текущей даты.
7. Не объясняй результат.
8. Верни только структуру по схеме.

Запрос пользователя:

{message}
"""

        result = await self._llm.ainvoke(prompt)

        return TripSpec.model_validate(result)