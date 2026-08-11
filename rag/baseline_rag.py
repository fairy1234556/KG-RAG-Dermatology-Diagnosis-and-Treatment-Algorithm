"""
Ordinary text RAG baseline for dermatology explanation experiments.

Pipeline:

    candidate disease + user observation
    -> BM25 flat-text retrieval
    -> Top-k evidence documents
    -> Qwen LLM
    -> unified structured result

This baseline does not use:

- semantic anchor mapping;
- graph traversal;
- graph relation weights;
- KG evidence path ranking.

Example:

    python rag/baseline_rag.py \
        --case-id CASE_001 \
        --disease "基底细胞癌" \
        --observation "患者面部出现光亮的珍珠样结节，表面可见细小血管。" \
        --top-k 5
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


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
from rag.text_retriever import BM25TextRetriever
from rag.text_retriever import RetrievedDocument


METHOD_DESCRIPTION = """
普通文本 RAG 基线。

本方法先从扁平医学证据语料库中检索与候选疾病和用户观察相关的
Top-k 文本片段，再将这些文本片段提供给大模型。

本方法不使用知识图谱关系、语义锚点、图遍历或证据路径排序。

额外限制：

1. 只能根据下方提供的检索文本组织外部证据。
2. 不得编造检索文本中没有出现的证据来源。
3. evidence_paths 必须为空，因为本方法不产生知识图谱路径。
4. sources 只能来自本次实际检索到的文本证据。
5. 检索文本未覆盖的信息必须写入 evidence_gap。
6. 候选疾病不能被表述为已经确诊。
""".strip()


def unique_non_empty(
    values: List[str],
) -> List[str]:
    """保留顺序，去除空值和重复值。"""

    result: List[str] = []

    for value in values:
        cleaned = (
            value or ""
        ).strip()

        if not cleaned:
            continue

        if cleaned not in result:
            result.append(cleaned)

    return result


def format_retrieved_context(
    documents: List[RetrievedDocument],
) -> str:
    """将 Top-k 文本证据格式化为模型上下文。"""

    if not documents:
        return (
            "本次普通文本检索没有返回可用证据。"
        )

    sections: List[str] = []

    for document in documents:
        source_text = (
            "；".join(document.source_names)
            if document.source_names
            else "未标注来源"
        )

        sections.extend(
            [
                f"[文档 {document.rank}]",
                f"文档编号：{document.document_id}",
                f"检索得分：{document.score:.6f}",
                f"证据文本：{document.text}",
                f"来源：{source_text}",
                "",
            ]
        )

    return "\n".join(sections).strip()


def collect_retrieved_sources(
    documents: List[RetrievedDocument],
) -> List[str]:
    """提取本次检索实际使用的来源名称。"""

    sources: List[str] = []

    for document in documents:
        sources.extend(
            list(document.source_names)
        )

    return unique_non_empty(sources)


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


def enforce_rag_baseline_boundary(
    result: KGRAGResult,
    retrieved_documents: List[
        RetrievedDocument
    ],
) -> KGRAGResult:
    """
    强制普通 RAG 的实验边界。

    - 不保留知识图谱路径；
    - 来源只能取自实际检索文档；
    - 检索为空时补充证据缺口说明。
    """

    evidence_gap = list(
        result.evidence_gap
    )

    if not retrieved_documents:
        gap_message = (
            "普通文本检索未返回可用证据，"
            "本次回答缺乏外部文本支持。"
        )

        if gap_message not in evidence_gap:
            evidence_gap.append(
                gap_message
            )

    retrieved_sources = (
        collect_retrieved_sources(
            retrieved_documents
        )
    )

    return _copy_result_with_updates(
        result,
        {
            "evidence_paths": [],
            "sources": retrieved_sources,
            "evidence_gap": evidence_gap,
        },
    )


def build_failed_result(
    case_id: str,
    candidate_disease: str,
    user_observation: str,
    error_message: str,
) -> KGRAGResult:
    """构造普通 RAG 的统一失败结果。"""

    return KGRAGResult(
        case_id=case_id.strip(),
        method="rag",
        candidate_disease=(
            candidate_disease.strip()
        ),
        user_observation=(
            user_observation.strip()
        ),
        evidence_paths=[],
        sources=[],
        evidence_gap=[
            "本次普通 RAG 运行失败，"
            "未生成有效的检索增强解释。"
        ],
        run_status="failed",
        error_message=error_message,
    )


class RAGBaseline:
    """普通文本检索增强对照方法。"""

    def __init__(
        self,
        retriever: Optional[
            BM25TextRetriever
        ] = None,
        client: Optional[
            QwenLLMClient
        ] = None,
    ) -> None:
        self.retriever = (
            retriever
            if retriever is not None
            else BM25TextRetriever()
        )

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
        top_k: int = 5,
    ) -> KGRAGResult:
        """运行一次普通文本 RAG 实验。"""

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

        if top_k <= 0:
            raise ValueError(
                "top_k 必须大于 0。"
            )

        retrieved_documents = (
            self.retriever.retrieve(
                candidate_disease=(
                    cleaned_disease
                ),
                user_observation=(
                    cleaned_observation
                ),
                top_k=top_k,
            )
        )

        evidence_context = (
            format_retrieved_context(
                retrieved_documents
            )
        )

        user_prompt = build_user_prompt(
            candidate_disease=(
                cleaned_disease
            ),
            user_observation=(
                cleaned_observation
            ),
            method_description=(
                METHOD_DESCRIPTION
            ),
            evidence_context=(
                evidence_context
            ),
        )

        llm_result = self.client.generate(
            user_prompt=user_prompt,
            system_prompt=(
                BASELINE_SYSTEM_PROMPT
            ),
            json_mode=True,
        )

        structured_result = (
            build_structured_result(
                case_id=cleaned_case_id,
                method="rag",
                candidate_disease=(
                    cleaned_disease
                ),
                user_observation=(
                    cleaned_observation
                ),
                llm_result=llm_result,
            )
        )

        return (
            enforce_rag_baseline_boundary(
                result=structured_result,
                retrieved_documents=(
                    retrieved_documents
                ),
            )
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "运行皮肤病辅助解释的普通文本 "
            "RAG 基线。"
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

    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="普通文本检索数量，默认 5",
    )

    args = parser.parse_args()

    try:
        baseline = RAGBaseline()

        result = baseline.run(
            case_id=args.case_id,
            candidate_disease=(
                args.disease
            ),
            user_observation=(
                args.observation
            ),
            top_k=args.top_k,
        )

    except (
        FileNotFoundError,
        ValueError,
        TypeError,
        LLMClientError,
        BaselineOutputError,
    ) as exc:
        result = build_failed_result(
            case_id=args.case_id,
            candidate_disease=(
                args.disease
            ),
            user_observation=(
                args.observation
            ),
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