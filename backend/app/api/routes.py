"""API routes definition."""

from datetime import datetime, timezone
from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter()


class HealthResponse(BaseModel):
    """Schema for health-check response."""
    status: str
    message: str
    timestamp: str
    version: str
    project: str


@router.get("/health", response_model=HealthResponse, tags=["Health"])
def health_check() -> HealthResponse:
    """
    Health-check endpoint.
    Used by frontend and monitoring agents to verify the backend server is reachable and active.
    """
    return HealthResponse(
        status="ok",
        message="FloatChat backend service is operational",
        timestamp=datetime.now(timezone.utc).isoformat(),
        version=settings.VERSION,
        project=settings.PROJECT_NAME,
    )


# Mount ARGO query endpoints under /argo
from app.api.argo_routes import router as argo_router
router.include_router(argo_router, prefix="/argo", tags=["ARGO Ocean Data"])

# Mount conversational chat endpoints under /chat
from app.api.chat_routes import router as chat_router
router.include_router(chat_router, prefix="/chat", tags=["Conversational Chat"])

