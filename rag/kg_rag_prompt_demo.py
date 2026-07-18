"""
Build a complete KG-RAG prompt from dermatology knowledge graph evidence.

Run from the project root:
    python rag/kg_rag_prompt_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional


# Keep imports stable when this file is executed directly from the project root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
KG_DIR = PROJECT_ROOT / "kg"

for import_path in (PROJECT_ROOT, KG_DIR):
    path_text = str(import_path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

try:
    from kg.kg_evidence_context_demo import EvidenceContextBuilder
except (ImportError, ModuleNotFoundError) as error:
    raise ImportError(
        "无法导入 EvidenceContextBuilder。请确认 "
        "kg/kg_evidence_context_demo.py 和 kg/kg_query_demo.py 存在，"
        "并从项目根目录运行：python rag/kg_rag_prompt_demo.py"
    ) from error


class KGRAGPromptBuilder:
    """Use knowledge graph evidence to assemble a constrained medical prompt."""

    def __init__(
        self, evidence_builder: Optional[EvidenceContextBuilder] = None
    ) -> None:
        self.evidence_builder = evidence_builder or EvidenceContextBuilder()

    def build_prompt(self, disease_name: str, user_observation: str) -> str:
        """Build a complete prompt for one candidate disease."""
        disease_name = disease_name.strip()
        user_observation = user_observation.strip()

        if not disease_name:
            raise ValueError("disease_name 不能为空。")
        if not user_observation:
            raise ValueError("user_observation 不能为空。")

        evidence_context = self.evidence_builder.build_context_by_disease(
            disease_name
        )

        return f"""一、任务说明
你是一名医学知识图谱辅助解释助手。请结合用户观察结果与下方知识图谱证据，对候选疾病进行谨慎、可追溯的解释。你的回答仅用于健康信息参考，不构成医学诊断。

二、用户输入/观察结果
- 候选疾病：{disease_name}
- 用户观察：{user_observation}

三、知识图谱证据上下文
{evidence_context}

四、生成要求
1. 只能基于给定的知识图谱证据生成解释，不得使用证据上下文之外的信息补充结论。
2. 不允许编造未在证据中出现的医学结论；证据不足时必须明确说明“给定证据不足”。
3. 不得给出处方、药物剂量或具体用药方案。
4. 不得替代医生诊断，不得将候选疾病表述为已经确诊。
5. 输出内容必须包括：候选疾病、支持证据、鉴别诊断、风险提示、就医建议。
6. 支持证据应尽量对应知识图谱中的证据路径或证据文本；没有对应证据的栏目应明确标注证据不足。

五、输出格式约束
请严格按照以下固定格式输出，不要增加或删除栏目：

候选疾病：
支持证据：
鉴别诊断：
风险提示：
就医建议："""


def build_prompt(disease_name: str, user_observation: str) -> str:
    """Convenience function for building a KG-RAG prompt."""
    return KGRAGPromptBuilder().build_prompt(disease_name, user_observation)


def main() -> None:
    """Run the requested basal cell carcinoma example."""
    try:
        prompt = build_prompt(
            "基底细胞癌",
            "患者皮损表现为珍珠样结节，表面可见血管，位于面部。",
        )
    except (ImportError, FileNotFoundError, ValueError) as error:
        print(f"KG-RAG Prompt 构建失败：{error}", file=sys.stderr)
        raise SystemExit(1) from error

    print(prompt)


if __name__ == "__main__":
    main()
