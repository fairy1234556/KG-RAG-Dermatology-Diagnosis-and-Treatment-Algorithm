from __future__ import annotations

from functools import lru_cache
from typing import List

from backend.app.schemas.knowledge_graph import DiseaseItem, EvidenceItem, FeatureDiseaseMatch, KGStatus
from backend.app.services.kg_repository import KGRepository


@lru_cache(maxsize=1)
def get_kg_repository() -> KGRepository:
    return KGRepository()


class KnowledgeGraphService:
    def __init__(self, repository: KGRepository | None = None) -> None:
        self.repository = repository or get_kg_repository()

    def status(self) -> KGStatus:
        return self.repository.status()

    def diseases(self) -> List[DiseaseItem]:
        return self.repository.diseases()

    def evidence_by_disease(self, disease_id: str) -> List[EvidenceItem]:
        return self.repository.evidence_by_disease(disease_id)

    def diseases_by_feature(self, feature: str) -> List[FeatureDiseaseMatch]:
        return self.repository.diseases_by_feature(feature)

