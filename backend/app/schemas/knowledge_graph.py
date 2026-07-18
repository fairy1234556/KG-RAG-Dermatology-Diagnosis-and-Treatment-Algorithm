from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class EntityRef(BaseModel):
    entity_id: str
    name_cn: str
    name_en: Optional[str] = ""
    entity_type: Optional[str] = None


class RelationRef(BaseModel):
    relation_cn: str
    relation_en: str


class EvidenceItem(BaseModel):
    triple_id: str
    head: EntityRef
    relation: RelationRef
    tail: EntityRef
    evidence_text: str = ""
    source_id: str = ""
    source_name: str = ""
    source_type: str = ""
    note: str = ""


class DiseaseItem(BaseModel):
    entity_id: str
    name_cn: str
    name_en: str = ""
    ham10000_label: str


class KGStatus(BaseModel):
    entity_count: int
    triple_count: int
    source_count: int
    disease_count: int
    csv_dir: str
    csv_available: bool
    loaded: bool
    warnings: List[str]


class FeatureDiseaseMatch(BaseModel):
    disease: DiseaseItem
    evidence: EvidenceItem


class EvidenceContextRequest(BaseModel):
    candidate_disease: str


class EvidenceContextResponse(BaseModel):
    structured_context: Dict[str, Any]
    markdown_context: str
    evidence_sections: Dict[str, List[EvidenceItem]]
    sources: List[Dict[str, str]]
    kg_status: KGStatus

