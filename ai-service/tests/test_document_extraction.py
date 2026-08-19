from datetime import date
from types import SimpleNamespace
from typing import Any

import pytest

from app.api.document_upload import validate_document_upload
from app.domain.documents import IdentityDocumentType, PassengerDocumentData, PassengerSex
from app.integrations.openai.document_extractor import PassengerDocumentExtractor


class CapturingResponses:
    def __init__(self) -> None:
        self.arguments: dict[str, Any] = {}

    async def parse(self, **kwargs: Any) -> SimpleNamespace:
        self.arguments = kwargs
        return SimpleNamespace(
            output_parsed=PassengerDocumentData(
                document_type=IdentityDocumentType.DOMESTIC_PASSPORT,
                first_name="Иван",
                last_name="Иванов",
                date_of_birth=date(1990, 1, 2),
                sex=PassengerSex.MALE,
                citizenship="RUS",
                document_series="1234",
                document_number="567890",
            )
        )


class CapturingClient:
    def __init__(self) -> None:
        self.responses = CapturingResponses()


@pytest.mark.parametrize(
    ("filename", "media_type", "content", "expected"),
    [
        ("document.png", "image/png", b"\x89PNG\r\n\x1a\n", "image/png"),
        ("document.jpg", "image/jpeg", b"\xff\xd8\xff", "image/jpeg"),
        ("document.pdf", "application/pdf", b"%PDF-1.7", "application/pdf"),
    ],
)
def test_validates_uploads(filename: str, media_type: str, content: bytes, expected: str) -> None:
    assert (
        validate_document_upload(
            filename=filename,
            declared_media_type=media_type,
            content=content,
        )
        == expected
    )


@pytest.mark.asyncio
async def test_uses_ephemeral_structured_responses_input() -> None:
    client = CapturingClient()
    extractor = PassengerDocumentExtractor(client, "gpt-test")  # type: ignore[arg-type]
    result = await extractor.extract(
        filename="document.pdf",
        media_type="application/pdf",
        content=b"%PDF-1.7",
    )
    arguments = client.responses.arguments
    assert result.document_number == "567890"
    assert arguments["store"] is False
    assert arguments["text_format"] is PassengerDocumentData
    assert arguments["input"][0]["content"][1]["type"] == "input_file"
