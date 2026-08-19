from datetime import date

import pytest

from app.document_uploads import validate_document_upload
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
