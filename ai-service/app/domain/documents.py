from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator

DocumentMediaType = Literal["image/png", "image/jpeg", "application/pdf"]


class IdentityDocumentType(StrEnum):
    INTERNATIONAL_PASSPORT = "international_passport"
    DOMESTIC_PASSPORT = "domestic_passport"
    BIRTH_CERTIFICATE = "birth_certificate"
    UNKNOWN = "unknown"


class PassengerSex(StrEnum):
    MALE = "male"
    FEMALE = "female"
    UNKNOWN = "unknown"


class PassengerDocumentData(BaseModel):
    document_type: IdentityDocumentType
    last_name: str | None = None
    first_name: str | None = None
    middle_name: str | None = None
    last_name_latin: str | None = None
    first_name_latin: str | None = None
    date_of_birth: date | None = None
    sex: PassengerSex
    citizenship: str | None = None
    document_series: str | None = None
    document_number: str | None = None
    issue_date: date | None = None
    expiration_date: date | None = None
    issuing_country: str | None = None
    issued_by: str | None = None
    place_of_birth: str | None = None
    warnings: list[str] = Field(default_factory=list)

    @field_validator(
        "last_name",
        "first_name",
        "middle_name",
        "last_name_latin",
        "first_name_latin",
        "citizenship",
        "document_series",
        "document_number",
        "issuing_country",
        "issued_by",
        "place_of_birth",
    )
    @classmethod
    def normalize_document_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


def missing_document_fields(document: PassengerDocumentData) -> list[str]:
    required = [
        "last_name",
        "first_name",
        "date_of_birth",
        "sex",
        "citizenship",
        "document_number",
    ]
    if document.document_type is IdentityDocumentType.INTERNATIONAL_PASSPORT:
        required.extend(
            ["last_name_latin", "first_name_latin", "expiration_date", "issuing_country"]
        )
    elif document.document_type in {
        IdentityDocumentType.DOMESTIC_PASSPORT,
        IdentityDocumentType.BIRTH_CERTIFICATE,
    }:
        required.append("document_series")
    missing = [
        field for field in required if getattr(document, field) in (None, "", PassengerSex.UNKNOWN)
    ]
    if document.document_type is IdentityDocumentType.UNKNOWN:
        missing.insert(0, "document_type")
    return list(dict.fromkeys(missing))
