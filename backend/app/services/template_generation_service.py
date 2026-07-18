from __future__ import annotations

from typing import Dict, List

from backend.app.schemas.common import AppError
from backend.app.schemas.knowledge_graph import EvidenceItem
from backend.app.schemas.kg_rag import TemplateGenerationResponse
from backend.app.services.evidence_context_service import EvidenceContextService


DISCLAIMER = "本结果仅用于辅助决策，不替代医生诊断；最终判断应由具备资质的医生结合面诊、皮肤镜、病理等临床信息作出。"


class TemplateGenerationService:
    def __init__(self, evidence_context_service: EvidenceContextService | None = None) -> None:
        self.evidence_context_service = evidence_context_service or EvidenceContextService()

    @staticmethod
    def _path(item: EvidenceItem) -> str:
        return f"{item.head.name_cn} — {item.relation.relation_cn} — {item.tail.name_cn}"

    @staticmethod
    def _source(item: EvidenceItem) -> str:
        extras = ", ".join(part for part in (item.source_id, item.source_type) if part)
        if item.source_name and extras:
            return f"{item.source_name} ({extras})"
        return item.source_name or extras or "未标注"

    def _item_dict(self, item: EvidenceItem) -> Dict[str, str]:
        return {
            "evidence_path": self._path(item),
            "evidence_text": item.evidence_text or "未标注",
            "source": self._source(item),
        }

    @staticmethod
    def _matches_observation(item: EvidenceItem, observation: str) -> bool:
        text = observation.lower()
        tail = item.tail.name_cn.lower()
        evidence = item.evidence_text.lower()
        if tail and tail in text:
            return True
        # Keep this conservative: match only meaningful phrases present in evidence text.
        return bool(evidence and any(part in evidence for part in text.split("，") if len(part) >= 4))

    def generate(self, candidate_disease: str, user_observation: str) -> TemplateGenerationResponse:
        if not candidate_disease.strip() or not user_observation.strip():
            raise AppError(
                "ANALYSIS_INSUFFICIENT_INPUT",
                "candidate_disease and user_observation are required.",
                status_code=400,
            )

        context = self.evidence_context_service.build(candidate_disease)
        sections = context.evidence_sections

        all_items: List[EvidenceItem] = [
            item for items in sections.values() for item in items
        ]
        observation_matches = [
            {
                "observation": user_observation.strip(),
                **self._item_dict(item),
                "match_note": "用户描述与图谱证据中的实体或证据文本存在对应关系。",
            }
            for item in all_items
            if self._matches_observation(item, user_observation)
        ]

        supporting_items = (
            sections.get("主要皮损表现", [])
            + sections.get("常见部位", [])
            + sections.get("伴随症状", [])
        )
        advice_items = sections.get("建议检查", []) + sections.get("就医建议", [])

        insufficient = []
        if not observation_matches:
            insufficient.append("给定证据不足：用户观察未能与当前图谱证据形成明确匹配。")
        if not sections.get("鉴别诊断"):
            insufficient.append("给定证据不足：当前图谱未提供可用鉴别诊断证据。")
        if not sections.get("风险提示"):
            insufficient.append("给定证据不足：当前图谱未提供可用风险提示证据。")

        return TemplateGenerationResponse(
            candidate_disease=candidate_disease.strip(),
            observation_evidence_matches=observation_matches,
            supporting_evidence=[self._item_dict(item) for item in supporting_items],
            differential_diagnosis=[
                self._item_dict(item) for item in sections.get("鉴别诊断", [])
            ],
            risk_warnings=[
                self._item_dict(item) for item in sections.get("风险提示", [])
            ],
            medical_advice_or_exams=[
                self._item_dict(item) for item in advice_items
            ],
            insufficient_evidence=insufficient or ["给定证据不足的内容：无。"],
            disclaimer=DISCLAIMER,
            generation_mode="template",
        )

