from typing import Annotated, Any

from fastapi import Depends, File, UploadFile

from app.agent.graph import get_agent
from app.integrations.openai.document_extractor import (
    PassengerDocumentExtractor,
    get_document_extractor,
)

AgentDep = Annotated[Any, Depends(get_agent)]
DocumentExtractorDep = Annotated[PassengerDocumentExtractor, Depends(get_document_extractor)]
DocumentUpload = Annotated[UploadFile, File(description="One PNG, JPEG, or PDF document.")]
