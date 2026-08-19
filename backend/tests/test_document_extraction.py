from datetime import date
from types import SimpleNamespace
from typing import Any

import pytest

from app.document_extraction import PassengerDocumentExtractor, validate_document_upload
from app.schemas import (
    IdentityDocumentType,
    PassengerDocumentData,
    PassengerSex,
    missing_document_fields,
)


@pytest.mark.parametrize(
    ("filename", "media_type", "content", "expected"),
    [
        ("document.png", "image/png", b"\x89PNG\r\n\x1a\n", "image/png"),
        ("document.jpg", "image/jpeg", b"\xff\xd8\xff", "image/jpeg"),
        ("document.jpeg", "image/jpg", b"\xff\xd8\xff", "image/jpeg"),
        ("document.pdf", "application/pdf", b"%PDF-1.7", "application/pdf"),
    ],
)
def test_validates_supported_document_uploads(
    filename: str,
    media_type: str,
    content: bytes,
    expected: str,
) -> None:
    assert (
        validate_document_upload(
            filename=filename,
            declared_media_type=media_type,
            content=content,
        )
        == expected
    )


def test_reports_missing_international_passport_fields() -> None:
    document = PassengerDocumentData(
        document_type=IdentityDocumentType.INTERNATIONAL_PASSPORT,
        last_name="ИВАНОВ",
        first_name="ИВАН",
        date_of_birth=date(1990, 1, 2),
        sex=PassengerSex.UNKNOWN,
        citizenship="RUS",
        document_number="1234567",
    )

    assert missing_document_fields(document) == [
        "sex",
        "last_name_latin",
        "first_name_latin",
        "expiration_date",
        "issuing_country",
    ]


class CapturingResponses:
    def __init__(self) -> None:
        self.arguments: dict[str, Any] = {}

    async def parse(self, **kwargs: Any) -> SimpleNamespace:
        self.arguments = kwargs
        document = PassengerDocumentData(
            document_type=IdentityDocumentType.DOMESTIC_PASSPORT,
            first_name="Иван",
            last_name="Иванов",
            date_of_birth=date(1990, 1, 2),
            sex=PassengerSex.MALE,
            citizenship="RUS",
            document_series="1234",
            document_number="567890",
        )
        return SimpleNamespace(output_parsed=document)


class CapturingClient:
    def __init__(self) -> None:
        self.responses = CapturingResponses()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("filename", "media_type", "content", "expected_input_type"),
    [
        ("document.jpg", "image/jpeg", b"\xff\xd8\xff", "input_image"),
        ("document.pdf", "application/pdf", b"%PDF-1.7", "input_file"),
    ],
)
async def test_sends_documents_as_ephemeral_structured_responses_inputs(
    filename: str,
    media_type: str,
    content: bytes,
    expected_input_type: str,
) -> None:
    client = CapturingClient()
    extractor = PassengerDocumentExtractor(client, "gpt-test")  # type: ignore[arg-type]

    result = await extractor.extract(
        filename=filename,
        media_type=media_type,  # type: ignore[arg-type]
        content=content,
    )

    arguments = client.responses.arguments
    document_input = arguments["input"][0]["content"][1]
    assert result.document_number == "567890"
    assert arguments["model"] == "gpt-test"
    assert arguments["text_format"] is PassengerDocumentData
    assert arguments["store"] is False
    assert document_input["type"] == expected_input_type
    assert document_input.get("image_url", document_input.get("file_data")).startswith("data:")
