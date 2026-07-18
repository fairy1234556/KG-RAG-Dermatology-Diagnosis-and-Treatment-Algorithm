from __future__ import annotations

from fastapi import APIRouter

from backend.app.schemas.common import ok
from backend.app.services.kg_service import KnowledgeGraphService

router = APIRouter(prefix="/kg", tags=["knowledge-graph"])


@router.get("/status")
def kg_status():
    return ok(KnowledgeGraphService().status().model_dump())


@router.get("/diseases")
def list_diseases():
    diseases = [item.model_dump() for item in KnowledgeGraphService().diseases()]
    return ok(diseases)


@router.get("/diseases/{disease_id}/evidence")
def disease_evidence(disease_id: str):
    evidence = [
        item.model_dump() for item in KnowledgeGraphService().evidence_by_disease(disease_id)
    ]
    return ok(evidence)


@router.get("/features/{feature}/diseases")
def feature_diseases(feature: str):
    matches = [
        item.model_dump() for item in KnowledgeGraphService().diseases_by_feature(feature)
    ]
    return ok(matches)
