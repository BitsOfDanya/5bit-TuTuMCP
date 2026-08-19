from fastapi import APIRouter, Depends

from app.api.routes import chat, documents
from app.core.security import verify_internal_token

api_router = APIRouter(
    prefix="/api/v1/ai",
    dependencies=[Depends(verify_internal_token)],
)
api_router.include_router(chat.router)
api_router.include_router(documents.router)
