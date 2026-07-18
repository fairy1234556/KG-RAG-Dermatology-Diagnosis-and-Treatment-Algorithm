from __future__ import annotations

from typing import Any, Dict, List

from backend.app.schemas.common import AppError
from backend.app.schemas.kg_rag import PromptResponse
from backend.app.services.evidence_context_service import EvidenceContextService
from backend.app.services.research_demo_adapters import ResearchDemoAdapter


SAFETY_CONSTRAINTS = [
    "仅用于辅助决策，不替代医生诊断。",
    "不得把候选疾病表述为确诊。",
    "不得输出处方、药物剂量或具体用药方案。",
    "不得虚构知识图谱之外的证据。",
    "证据不足时必须明确写“给定证据不足”。",
    "不得输出患病概率。",
    "V1.0 不实现图片分类。",
]


class PromptService:
    def __init__(
        self,
        evidence_context_service: EvidenceContextService | None = None,
        demo_adapter: ResearchDemoAdapter | None = None,
    ) -> None:
        self.evidence_context_service = evidence_context_service or EvidenceContextService()
        self.demo_adapter = demo_adapter or ResearchDemoAdapter()

    def build_prompt(
        self,
        candidate_disease: str,
        user_observation: str,
        prompt_version: str | None = "doctor_kg_rag_v1",
    ) -> PromptResponse:
        if not candidate_disease.strip() or not user_observation.strip():
            raise AppError(
                "ANALYSIS_INSUFFICIENT_INPUT",
                "candidate_disease and user_observation are required.",
                status_code=400,
            )

        context = self.evidence_context_service.build(candidate_disease)
        safety_text = "\n".join(f"{idx + 1}. {item}" for idx, item in enumerate(SAFETY_CONSTRAINTS))
        version = prompt_version or "doctor_kg_rag_v1"

        fallback_prompt_text = f"""一、任务说明
你是一名医学知识图谱辅助解释助手。请结合用户观察结果与下方知识图谱证据，对候选疾病进行谨慎、可追溯的解释。你的回答仅用于健康信息参考，不构成医学诊断。

二、用户输入/观察结果
- 候选疾病：{candidate_disease.strip()}
- 用户观察：{user_observation.strip()}

三、知识图谱证据上下文
{context.markdown_context}

四、医学安全限制
{safety_text}

五、输出格式约束
请严格按照以下固定格式输出，不要增加或删除一级栏目：

候选疾病：
用户观察与证据匹配：
支持证据：
鉴别诊断：
风险提示：
就医/检查建议：
证据不足说明：
免责声明："""

        try:
            if version == "doctor_kg_rag_v2":
                prompt_text = self.demo_adapter.build_prompt_v2(
                    candidate_disease.strip(), user_observation.strip()
                )
            elif version == "doctor_kg_rag_v1":
                prompt_text = self.demo_adapter.build_prompt_v1(
                    candidate_disease.strip(), user_observation.strip()
                )
            else:
                prompt_text = fallback_prompt_text
        except Exception:
            prompt_text = fallback_prompt_text

        if "不得输出患病概率" not in prompt_text:
            prompt_text = f"{prompt_text}\n\n六、阶段一统一安全补充\n{safety_text}"

        evidence_summary: Dict[str, Any] = {
            "section_count": len(context.evidence_sections),
            "source_count": len(context.sources),
            "sections": {
                section: len(items) for section, items in context.evidence_sections.items()
            },
        }
        return PromptResponse(
            prompt_text=prompt_text,
            candidate_disease=candidate_disease.strip(),
            evidence_summary=evidence_summary,
            prompt_version=version,
            safety_constraints=SAFETY_CONSTRAINTS,
        )


def safety_constraints() -> List[str]:
    return list(SAFETY_CONSTRAINTS)
