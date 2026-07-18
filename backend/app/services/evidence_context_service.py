from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from backend.app.schemas.common import AppError
from backend.app.schemas.knowledge_graph import EvidenceContextResponse, EvidenceItem
from backend.app.services.kg_repository import KGRepository
from backend.app.services.kg_service import get_kg_repository


class EvidenceContextService:
    RELATION_TO_SECTION = {
        "has_manifestation": "主要皮损表现",
        "commonly_occurs_at": "常见部位",
        "has_symptom": "伴随症状",
        "recommended_examination": "建议检查",
        "differential_diagnosis": "鉴别诊断",
        "has_risk_warning": "风险提示",
        "has_medical_advice": "就医建议",
    }

    SECTION_ORDER = [
        "候选疾病",
        "主要皮损表现",
        "常见部位",
        "伴随症状",
        "建议检查",
        "鉴别诊断",
        "风险提示",
        "就医建议",
        "证据来源",
    ]

    def __init__(self, repository: KGRepository | None = None) -> None:
        self.repository = repository or get_kg_repository()

    @staticmethod
    def _path_text(item: EvidenceItem) -> str:
        return f"{item.head.name_cn} — {item.relation.relation_cn} — {item.tail.name_cn}"

    @staticmethod
    def _source_text(item: EvidenceItem) -> str:
        extras = ", ".join(part for part in (item.source_id, item.source_type) if part)
        if item.source_name and extras:
            return f"{item.source_name} ({extras})"
        return item.source_name or extras or "未标注"

    def _format_item(self, item: EvidenceItem) -> str:
        return "\n".join(
            [
                f"- 证据路径：{self._path_text(item)}",
                f"  evidence_text：{item.evidence_text or '未标注'}",
                f"  source：{self._source_text(item)}",
            ]
        )

    @staticmethod
    def _format_section(title: str, lines: List[str]) -> str:
        content = lines or ["- 暂无相关证据。"]
        return f"## {title}\n" + "\n".join(content)

    def build(self, candidate_disease: str) -> EvidenceContextResponse:
        if not candidate_disease.strip():
            raise AppError(
                "ANALYSIS_INSUFFICIENT_INPUT",
                "candidate_disease is required.",
                status_code=400,
            )

        disease = self.repository.find_disease(candidate_disease)
        evidence = self.repository.evidence_by_disease(candidate_disease)

        evidence_sections: Dict[str, List[EvidenceItem]] = defaultdict(list)
        for item in evidence:
            section = self.RELATION_TO_SECTION.get(item.relation.relation_en)
            if section:
                evidence_sections[section].append(item)

        labels = self.repository._split_list_field(disease.get("alias", ""))
        structured_context = {
            "candidate_disease": {
                "entity_id": disease.get("id", ""),
                "name_cn": disease.get("name_cn", ""),
                "name_en": disease.get("name_en", ""),
                "ham10000_label": labels[0] if labels else "",
            },
            "sections": {
                section: [item.model_dump() for item in items]
                for section, items in evidence_sections.items()
            },
        }

        source_lines = [
            f"- {source['source_name']} ({source['source_id']}, {source['source_type']})".strip()
            for source in self.repository.sources_from_evidence(evidence)
        ]

        markdown_sections: Dict[str, List[str]] = {
            "候选疾病": [
                f"- {disease.get('name_cn', '')} / {disease.get('name_en', '')}（{disease.get('id', '')}）"
            ],
            "证据来源": source_lines,
        }
        for section, items in evidence_sections.items():
            markdown_sections[section] = [self._format_item(item) for item in items]

        markdown_context = "\n\n".join(
            self._format_section(section, markdown_sections.get(section, []))
            for section in self.SECTION_ORDER
        )

        return EvidenceContextResponse(
            structured_context=structured_context,
            markdown_context=markdown_context,
            evidence_sections=dict(evidence_sections),
            sources=self.repository.sources_from_evidence(evidence),
            kg_status=self.repository.status(),
        )
