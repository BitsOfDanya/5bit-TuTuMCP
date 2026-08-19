from pathlib import Path
from typing import Literal

DocumentMediaType = Literal["image/png", "image/jpeg", "application/pdf"]
SUPPORTED_EXTENSIONS: dict[str, DocumentMediaType] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".pdf": "application/pdf",
}
SUPPORTED_MEDIA_TYPES = set(SUPPORTED_EXTENSIONS.values())


def validate_document_upload(
    *,
    filename: str | None,
    declared_media_type: str | None,
    content: bytes,
) -> DocumentMediaType:
    normalized = "image/jpeg" if declared_media_type == "image/jpg" else declared_media_type
    if normalized not in SUPPORTED_MEDIA_TYPES:
        raise ValueError("Only PNG, JPEG, and PDF documents are supported.")
    suffix = Path(filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError("The filename must have a .png, .jpg, .jpeg, or .pdf extension.")
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        detected: DocumentMediaType = "image/png"
    elif content.startswith(b"\xff\xd8\xff"):
        detected = "image/jpeg"
    elif content.startswith(b"%PDF-"):
        detected = "application/pdf"
    else:
        raise ValueError("The uploaded file signature is not a valid PNG, JPEG, or PDF.")
    if SUPPORTED_EXTENSIONS[suffix] != detected:
        raise ValueError("The filename extension does not match the uploaded file.")
    if normalized != detected:
        raise ValueError("The Content-Type does not match the uploaded file.")
    return detected
