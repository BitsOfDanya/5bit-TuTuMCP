import logging

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import DocumentExtractorDep, DocumentUpload
from app.api.document_upload import (
    DocumentMediaType,
    extension_for,
    validate_document_upload,
)
from app.api.schemas import DocumentExtractionResponse
from app.core.config import get_settings
from app.domain.documents import missing_document_fields

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/extract")
async def extract_document(
    document: DocumentUpload,
    extractor: DocumentExtractorDep,
) -> DocumentExtractionResponse:
    max_size = get_settings().max_document_size_bytes
    content = await document.read(max_size + 1)
    if len(content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"The document exceeds the {max_size // (1024 * 1024)} MB limit.",
        )
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The uploaded document is empty.",
        )
    try:
        media_type: DocumentMediaType = validate_document_upload(
            filename=document.filename,
            declared_media_type=document.content_type,
            content=content,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        ) from exc

    try:
        extracted = await extractor.extract(
            filename=f"document{extension_for(media_type)}",
            media_type=media_type,
            content=content,
        )
    except Exception as exc:
        logger.exception("Passenger document extraction failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The passenger document could not be extracted.",
        ) from exc
    missing_fields = missing_document_fields(extracted)
    return DocumentExtractionResponse(
        media_type=media_type,
        document=extracted,
        missing_fields=missing_fields,
        manual_review_required=bool(missing_fields or extracted.warnings),
    )
