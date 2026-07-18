from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, Iterable, List, Optional

from backend.app.core.config import settings
from backend.app.schemas.common import AppError
from backend.app.schemas.knowledge_graph import (
    DiseaseItem,
    EntityRef,
    EvidenceItem,
    FeatureDiseaseMatch,
    KGStatus,
    RelationRef,
)


class KGRepository:
    """Adapter around the existing CSV knowledge graph demo code."""

    REQUIRED_FILES = (
        "entity_nodes.csv",
        "triples.csv",
        "source_references.csv",
    )

    def __init__(
        self,
        csv_dir: Optional[Path] = None,
        demo_path: Optional[Path] = None,
    ) -> None:
        self.csv_dir = (csv_dir or settings.kg_csv_dir).resolve()
        self.demo_path = (demo_path or settings.kg_query_demo_path).resolve()
        self._module: Optional[ModuleType] = None
        self._query: Any = None
        self._load_errors: List[str] = []
        self._load()

    def _load_demo_module(self) -> ModuleType:
        if not self.demo_path.exists():
            raise AppError(
                "KG_FILE_NOT_FOUND",
                f"KG query demo file not found: {self.demo_path}",
                status_code=500,
            )

        spec = importlib.util.spec_from_file_location(
            "stage1_kg_query_demo_adapter", self.demo_path
        )
        if spec is None or spec.loader is None:
            raise AppError(
                "KG_LOAD_FAILED",
                f"Cannot load KG query demo from: {self.demo_path}",
                status_code=500,
            )

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _load(self) -> None:
        missing = [name for name in self.REQUIRED_FILES if not (self.csv_dir / name).exists()]
        if missing:
            raise AppError(
                "KG_FILE_NOT_FOUND",
                f"Required KG CSV file(s) not found in {self.csv_dir}: {', '.join(missing)}",
                status_code=500,
            )

        try:
            self._module = self._load_demo_module()
            query_cls = getattr(self._module, "KnowledgeGraphQuery")
            self._query = query_cls(csv_dir=self.csv_dir)
        except AppError:
            raise
        except Exception as exc:  # pragma: no cover - defensive startup path
            raise AppError(
                "KG_LOAD_FAILED",
                f"Failed to load KG CSV files: {exc}",
                status_code=500,
            ) from exc

    @property
    def query(self) -> Any:
        return self._query

    def _warnings(self) -> List[str]:
        warnings: List[str] = []
        if self.entity_count != settings.kg_expected_entities:
            warnings.append(
                f"Expected {settings.kg_expected_entities} effective entities, got {self.entity_count}."
            )
        if self.triple_count != settings.kg_expected_triples:
            warnings.append(
                f"Expected {settings.kg_expected_triples} triples, got {self.triple_count}."
            )
        if self.source_count != settings.kg_expected_sources:
            warnings.append(
                f"Expected {settings.kg_expected_sources} sources, got {self.source_count}."
            )
        if len(self.diseases()) != settings.kg_expected_diseases:
            warnings.append(
                f"Expected {settings.kg_expected_diseases} HAM10000 diseases, got {len(self.diseases())}."
            )
        return warnings

    @property
    def entity_count(self) -> int:
        return len(self.query.entities)

    @property
    def triple_count(self) -> int:
        return len(self.query.triples)

    @property
    def source_count(self) -> int:
        return len(self.query.sources)

    def status(self) -> KGStatus:
        return KGStatus(
            entity_count=self.entity_count,
            triple_count=self.triple_count,
            source_count=self.source_count,
            disease_count=len(self.diseases()),
            csv_dir=str(self.csv_dir),
            csv_available=all((self.csv_dir / name).exists() for name in self.REQUIRED_FILES),
            loaded=True,
            warnings=self._warnings(),
        )

    @staticmethod
    def _split_list_field(value: str) -> List[str]:
        for separator in (";", "；", "，", "|"):
            value = value.replace(separator, ",")
        return [item.strip() for item in value.split(",") if item.strip()]

    @staticmethod
    def _norm(value: str) -> str:
        return value.strip().lower()

    def _entity_matches(self, entity: Dict[str, str], query: str) -> bool:
        candidates = [
            entity.get("id", ""),
            entity.get("name_cn", ""),
            entity.get("name_en", ""),
        ]
        candidates.extend(self._split_list_field(entity.get("alias", "")))
        normalized_query = self._norm(query)
        return any(self._norm(candidate) == normalized_query for candidate in candidates)

    def find_entity(self, query: str, entity_type: Optional[str] = None) -> Dict[str, str]:
        for entity in self.query.entities:
            if entity_type and entity.get("entity_type") != entity_type:
                continue
            if self._entity_matches(entity, query):
                return entity
        raise AppError(
            "KG_ENTITY_NOT_FOUND",
            f"Knowledge graph entity not found: {query}",
            status_code=404,
        )

    def find_disease(self, disease: str) -> Dict[str, str]:
        try:
            return self.find_entity(disease, "Disease")
        except AppError as exc:
            raise AppError(
                "KG_DISEASE_NOT_FOUND",
                f"Disease not found in HAM10000 V1.0 scope: {disease}",
                status_code=404,
            ) from exc

    def diseases(self) -> List[DiseaseItem]:
        items: List[DiseaseItem] = []
        for entity in self.query.entities:
            if entity.get("entity_type") != "Disease":
                continue
            labels = self._split_list_field(entity.get("alias", ""))
            items.append(
                DiseaseItem(
                    entity_id=entity.get("id", ""),
                    name_cn=entity.get("name_cn", ""),
                    name_en=entity.get("name_en", ""),
                    ham10000_label=labels[0] if labels else "",
                )
            )
        return items

    def _source_for_triple(self, triple_id: str) -> Dict[str, str]:
        return self.query.sources_by_triple_id.get(triple_id, {})

    def _entity_ref(self, entity_id: str, name_cn: str, entity_type: str) -> EntityRef:
        entity = self.query.entities_by_id.get(entity_id, {})
        return EntityRef(
            entity_id=entity_id,
            name_cn=entity.get("name_cn") or name_cn,
            name_en=entity.get("name_en", ""),
            entity_type=entity.get("entity_type") or entity_type,
        )

    def evidence_item(self, triple: Dict[str, str]) -> EvidenceItem:
        source = self._source_for_triple(triple.get("triple_id", ""))
        return EvidenceItem(
            triple_id=triple.get("triple_id", ""),
            head=self._entity_ref(
                triple.get("head_id", ""),
                triple.get("head_cn", ""),
                triple.get("head_type", ""),
            ),
            relation=RelationRef(
                relation_cn=triple.get("relation_cn", ""),
                relation_en=triple.get("relation_en", ""),
            ),
            tail=self._entity_ref(
                triple.get("tail_id", ""),
                triple.get("tail_cn", ""),
                triple.get("tail_type", ""),
            ),
            evidence_text=triple.get("evidence_text", ""),
            source_id=source.get("source_id", ""),
            source_name=source.get("source_name", "") or triple.get("source", ""),
            source_type=source.get("source_type", ""),
            note=triple.get("note", ""),
        )

    def evidence_by_disease(self, disease: str) -> List[EvidenceItem]:
        self.find_disease(disease)
        triples = self.query.query_by_disease(disease)
        if not triples:
            raise AppError(
                "KG_EVIDENCE_NOT_FOUND",
                f"No evidence found for disease: {disease}",
                status_code=404,
            )
        return [self.evidence_item(triple) for triple in triples]

    def diseases_by_feature(self, feature: str) -> List[FeatureDiseaseMatch]:
        self.find_entity(feature)
        triples = self.query.query_by_feature(feature)
        if not triples:
            raise AppError(
                "KG_EVIDENCE_NOT_FOUND",
                f"No disease evidence found for feature: {feature}",
                status_code=404,
            )

        matches: List[FeatureDiseaseMatch] = []
        for triple in triples:
            disease = self.find_disease(triple.get("head_id", ""))
            labels = self._split_list_field(disease.get("alias", ""))
            matches.append(
                FeatureDiseaseMatch(
                    disease=DiseaseItem(
                        entity_id=disease.get("id", ""),
                        name_cn=disease.get("name_cn", ""),
                        name_en=disease.get("name_en", ""),
                        ham10000_label=labels[0] if labels else "",
                    ),
                    evidence=self.evidence_item(triple),
                )
            )
        return matches

    def sources_from_evidence(self, evidence: Iterable[EvidenceItem]) -> List[Dict[str, str]]:
        seen = set()
        sources: List[Dict[str, str]] = []
        for item in evidence:
            key = item.source_id or item.source_name
            if not key or key in seen:
                continue
            seen.add(key)
            sources.append(
                {
                    "source_id": item.source_id,
                    "source_name": item.source_name,
                    "source_type": item.source_type,
                }
            )
        return sources

