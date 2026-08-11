"""
Pure LLM baseline for dermatology explanation experiments.

This baseline receives only:

1. Candidate disease.
2. User observation.

It does not receive retrieved documents or knowledge graph evidence.

Run:

    python rag/baseline_llm.py \
        --case-id CASE_001 \
        --disease "基底细胞癌" \
        --observation "患者面部出现珍珠样结节，表面可见细小血管。"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from rag.baseline_common import BASELINE_SYSTEM_PROMPT
from rag.baseline_common import BaselineOutputError
from rag.baseline_common import build_structured_result
from rag.baseline_common import build_user_prompt
from rag.baseline_common import result_to_dict
from rag.llm_client import LLMClientError
from rag.llm_client import QwenLLMClient
from rag.schemas import KGRAGResult


METHOD_DESCRIPTION = """
纯 LLM 基线。

本方法不提供知识图谱、检索文本、医学文献片段或其他外部证据。
你只能根据候选疾病、用户观察以及模型自身已有知识进行谨慎解释。

额外限制：

1. sources 必须返回空数组。
2. 不得声称引用了某个网站、论文、指南或数据库。
3. 不得生成具体的知识图谱证据路径。
4. supporting_evidence 只能表述为一般医学知识，不能伪装成检索证据。
5. evidence_gap 中应说明本方法没有接入外部可追溯证据。
""".strip()


def _copy_result_with_updates(
    result: KGRAGResult,
    updates: Dict[str, Any],
) -> KGRAGResult:
    """兼容 Pydantic V1 和 V2 的模型复制。"""

    if hasattr(result, "model_copy"):
        return result.model_copy(
            update=updates
        )

    return result.copy(
        update=updates
    )


def enforce_llm_baseline_boundary(
    result: KGRAGResult,
) -> KGRAGResult:
    """
    强制纯 LLM 基线遵守实验边界。

    即使模型生成了来源名称，也不允许将其作为真实引用来源。
    """

    evidence_gap = list(
        result.evidence_gap
    )

    boundary_message = (
        "纯 LLM 基线未接入外部检索证据，"
        "回答中的医学内容不具备本次运行级别的来源追溯能力。"
    )

    if boundary_message not in evidence_gap:
        evidence_gap.append(
            boundary_message
        )

    return _copy_result_with_updates(
        result,
        {
            "evidence_paths": [],
            "sources": [],
            "evidence_gap": evidence_gap,
        },
    )


def build_failed_result(
    case_id: str,
    candidate_disease: str,
    user_observation: str,
    error_message: str,
) -> KGRAGResult:
    """构造统一的失败结果。"""

    return KGRAGResult(
        case_id=case_id.strip(),
        method="llm",
        candidate_disease=(
            candidate_disease.strip()
        ),
        user_observation=(
            user_observation.strip()
        ),
        evidence_paths=[],
        sources=[],
        evidence_gap=[
            "本次模型调用失败，未生成有效解释。"
        ],
        run_status="failed",
        error_message=error_message,
    )


class LLMBaseline:
    """纯大模型对照方法。"""

    def __init__(
        self,
        client: QwenLLMClient = None,
    ) -> None:
        self.client = (
            client
            if client is not None
            else QwenLLMClient()
        )

    def run(
        self,
        case_id: str,
        candidate_disease: str,
        user_observation: str,
    ) -> KGRAGResult:
        """运行一次纯 LLM 基线实验。"""

        cleaned_case_id = (
            case_id or ""
        ).strip()

        cleaned_disease = (
            candidate_disease or ""
        ).strip()

        cleaned_observation = (
            user_observation or ""
        ).strip()

        if not cleaned_case_id:
            raise ValueError(
                "case_id 不能为空。"
            )

        if not cleaned_disease:
            raise ValueError(
                "candidate_disease 不能为空。"
            )

        if not cleaned_observation:
            raise ValueError(
                "user_observation 不能为空。"
            )

        user_prompt = build_user_prompt(
            candidate_disease=cleaned_disease,
            user_observation=cleaned_observation,
            method_description=METHOD_DESCRIPTION,
            evidence_context="",
        )

        llm_result = self.client.generate(
            user_prompt=user_prompt,
            system_prompt=BASELINE_SYSTEM_PROMPT,
            json_mode=True,
        )

        structured_result = (
            build_structured_result(
                case_id=cleaned_case_id,
                method="llm",
                candidate_disease=cleaned_disease,
                user_observation=(
                    cleaned_observation
                ),
                llm_result=llm_result,
            )
        )

        return enforce_llm_baseline_boundary(
            structured_result
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "运行皮肤病辅助解释的纯 LLM 基线。"
        )
    )

    parser.add_argument(
        "--case-id",
        required=True,
        help="实验样例编号",
    )

    parser.add_argument(
        "--disease",
        required=True,
        help="候选疾病名称",
    )

    parser.add_argument(
        "--observation",
        required=True,
        help="用户观察文本",
    )

    args = parser.parse_args()

    baseline = None

    try:
        baseline = LLMBaseline()

        result = baseline.run(
            case_id=args.case_id,
            candidate_disease=args.disease,
            user_observation=args.observation,
        )

    except (
        FileNotFoundError,
        ValueError,
        LLMClientError,
        BaselineOutputError,
    ) as exc:
        result = build_failed_result(
            case_id=args.case_id,
            candidate_disease=args.disease,
            user_observation=args.observation,
            error_message=str(exc),
        )

    print(
        json.dumps(
            result_to_dict(result),
            ensure_ascii=False,
            indent=2,
        )
    )

    return (
        0
        if result.run_status == "success"
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())