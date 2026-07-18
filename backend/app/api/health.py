from __future__ import annotations

from fastapi import APIRouter

from backend.app.core.config import settings
from backend.app.schemas.common import ok
from backend.app.services.kg_service import KnowledgeGraphService

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    kg_status = KnowledgeGraphService().status()
    return ok(
        {
            "service_status": "ok",
            "system_version": settings.system_version,
            "kg_loaded": kg_status.loaded,
            "kg_warnings": kg_status.warnings,
        }
    )

