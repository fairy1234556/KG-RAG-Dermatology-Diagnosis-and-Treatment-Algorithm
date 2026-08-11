"""
Knowledge-graph-enhanced RAG pipeline for dermatology explanation.

Pipeline:

    candidate disease + user observation
    -> semantic anchor recognition
    -> graph path retrieval
    -> evidence path ranking
    -> Top-k graph evidence context
    -> Qwen LLM
    -> unified structured result

Example:

    python rag/kg_rag_pipeline.py \
        --case-id CASE_001 \
        --disease "基底细胞癌" \
        --observation "患者面部出现光亮的珍珠样结节，表面可见细小血管。" \
        --top-k 5 \
        --max-hops 2
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


from kg.path_ranker import EvidencePathRanker
from kg.path_ranker import RankedEvidencePath
from rag.baseline_common import BASELINE_SYSTEM_PROMPT
from rag.baseline_common import BaselineOutputError
from rag.baseline_common import build_structured_result
from rag.baseline_common import build_user_prompt
from rag.baseline_common import result_to_dict
from rag.llm_client import LLMClientError
from rag.llm_client import QwenLLMClient
from rag.schemas import EvidencePath as SchemaEvidencePath
from rag.schemas import KGRAGResult


METHOD_DESCRIPTION = """
知识图谱增强 KG-RAG 方法。

本方法先从用户观察文本中识别语义锚点，将观察表达映射到标准医学实体；
再从候选疾病出发检索一跳和受限二跳知识图谱路径；
随后依据实体匹配、关系权重、候选疾病匹配和路径长度惩罚进行排序，
最终将 Top-k 可追溯证据链提供给大模型。

额外限制：

1. 只能将下方提供的图谱证据链表述为外部证据。
2. 不得编造不存在的实体、关系、证据文本或来源。
3. supporting_evidence 应优先使用与语义锚点直接匹配的路径。
4. 二跳鉴别路径只能作为辅助鉴别信息，不能当作候选疾病直接证据。
5. sources 只能来自本次实际使用的图谱证据链。
6. evidence_gap 必须说明观察中缺失、冲突或无法确认的内容。
7. 候选疾病不能被表述为已经确诊。
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


def format_path_text(
    ranked_path: RankedEvidencePath,
) -> str:
    """将一条图谱路径格式化为可读文本。"""

    path_parts: List[str] = []

    for index, edge in enumerate(
        ranked_path.path.edges
    ):
        if index == 0:
            path_parts.append(
                edge.head_name
            )

        path_parts.append(
            edge.relation_cn
        )

        path_parts.append(
            edge.tail_name
        )

    return " → ".join(path_parts)


def format_kg_evidence_context(
    ranked_paths: List[RankedEvidencePath],
    retrieved_path_count: int,
) -> str:
    """构造发送给大模型的 Top-k 图谱证据上下文。"""

    if not ranked_paths:
        return (
            "本次没有检索到可用的知识图谱证据链。"
        )

    sections: List[str] = [
        f"检索路径总数：{retrieved_path_count}",
        f"进入模型的 Top-k 路径数：{len(ranked_paths)}",
        "",
    ]

    for result in ranked_paths:
        path_text = format_path_text(
            result
        )

        matched_anchors = (
            "；".join(
                result.matched_anchor_names
            )
            if result.matched_anchor_names
            else "无直接语义锚点匹配"
        )

        evidence_text = (
            "；".join(
                result.evidence_texts
            )
            if result.evidence_texts
            else "未标注"
        )

        source_text = (
            "；".join(
                result.source_names
            )
            if result.source_names
            else "未标注"
        )

        sections.extend(
            [
                f"[证据链 Rank {result.rank}]",
                f"路径编号：{result.path_id}",
                f"路径：{path_text}",
                f"路径跳数：{result.hop_count}",
                f"终点实体：{result.end_entity_name} "
                f"({result.end_entity_id})",
                f"匹配语义锚点：{matched_anchors}",
                (
                    "评分："
                    f"总分={result.total_score:.4f}，"
                    f"实体匹配分={result.entity_match_score:.4f}，"
                    f"关系权重分={result.relation_weight_score:.4f}，"
                    f"疾病匹配分={result.disease_match_score:.4f}，"
                    f"路径惩罚={result.path_length_penalty:.4f}"
                ),
                f"证据文本：{evidence_text}",
                f"来源：{source_text}",
                "",
            ]
        )

    return "\n".join(sections).strip()


def collect_ranked_sources(
    ranked_paths: List[RankedEvidencePath],
) -> List[str]:
    """提取 Top-k 路径实际使用的来源。"""

    sources: List[str] = []

    for result in ranked_paths:
        sources.extend(
            list(result.source_names)
        )

    return unique_non_empty(sources)


def convert_ranked_path(
    ranked_path: RankedEvidencePath,
) -> SchemaEvidencePath:
    """将任务三路径结果转换为统一输出结构。"""

    path_texts = [
        edge.evidence_text
        for edge in ranked_path.path.edges
        if edge.evidence_text.strip()
    ]

    triple_ids = [
        edge.triple_id
        for edge in ranked_path.path.edges
        if edge.triple_id.strip()
    ]

    relation_names = [
        edge.relation_cn
        for edge in ranked_path.path.edges
        if edge.relation_cn.strip()
    ]

    return SchemaEvidencePath(
        head_entity=(
            ranked_path.start_disease_name
        ),
        relation=" → ".join(
            relation_names
        ),
        tail_entity=(
            ranked_path.end_entity_name
        ),
        evidence_text="；".join(
            unique_non_empty(path_texts)
        ),
        source_id="；".join(
            unique_non_empty(triple_ids)
        ),
        source_name="；".join(
            list(ranked_path.source_names)
        ),
        score=ranked_path.total_score,
    )


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


def enforce_kg_rag_boundary(
    result: KGRAGResult,
    ranked_paths: List[RankedEvidencePath],
    anchor_count: int,
) -> KGRAGResult:
    """
    强制 KG-RAG 结果使用实际路径和实际来源。

    模型不能自行决定 evidence_paths 和 sources。
    """

    evidence_gap = list(
        result.evidence_gap
    )

    if anchor_count == 0:
        gap_message = (
            "用户观察未识别出可靠语义锚点，"
            "当前图谱证据主要属于候选疾病的一般知识，"
            "不能视为用户个体的直接匹配证据。"
        )

        if gap_message not in evidence_gap:
            evidence_gap.append(
                gap_message
            )

    if not ranked_paths:
        gap_message = (
            "知识图谱未返回可用证据链，"
            "本次解释缺乏图谱证据支持。"
        )

        if gap_message not in evidence_gap:
            evidence_gap.append(
                gap_message
            )

    evidence_paths = [
        convert_ranked_path(path)
        for path in ranked_paths
    ]

    sources = collect_ranked_sources(
        ranked_paths
    )

    return _copy_result_with_updates(
        result,
        {
            "evidence_paths": evidence_paths,
            "sources": sources,
            "evidence_gap": evidence_gap,
        },
    )


def build_failed_result(
    case_id: str,
    candidate_disease: str,
    user_observation: str,
    error_message: str,
) -> KGRAGResult:
    """构造 KG-RAG 的统一失败结果。"""

    return KGRAGResult(
        case_id=case_id.strip(),
        method="kg_rag",
        candidate_disease=(
            candidate_disease.strip()
        ),
        user_observation=(
            user_observation.strip()
        ),
        evidence_paths=[],
        sources=[],
        evidence_gap=[
            "本次 KG-RAG 运行失败，"
            "未生成有效的知识图谱增强解释。"
        ],
        run_status="failed",
        error_message=error_message,
    )


class KGRAGPipeline:
    """知识图谱增强 RAG 主流程。"""

    def __init__(
        self,
        ranker: Optional[
            EvidencePathRanker
        ] = None,
        client: Optional[
            QwenLLMClient
        ] = None,
    ) -> None:
        self.ranker = (
            ranker
            if ranker is not None
            else EvidencePathRanker()
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
        max_hops: int = 2,
    ) -> KGRAGResult:
        """运行一次 KG-RAG 实验。"""

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

        if max_hops not in {1, 2}:
            raise ValueError(
                "max_hops 当前只允许为 1 或 2。"
            )

        (
            anchors,
            ranked_paths,
            retrieved_path_count,
        ) = self.ranker.rank(
            disease_query=cleaned_disease,
            observation_text=(
                cleaned_observation
            ),
            top_k=top_k,
            max_hops=max_hops,
        )

        evidence_context = (
            format_kg_evidence_context(
                ranked_paths=ranked_paths,
                retrieved_path_count=(
                    retrieved_path_count
                ),
            )
        )

        anchor_context = (
            "；".join(
                (
                    f"{anchor.matched_text}"
                    f" → {anchor.entity_name}"
                    f" ({anchor.entity_id}, "
                    f"置信度={anchor.confidence:.2f})"
                )
                for anchor in anchors
            )
            if anchors
            else "未识别出可靠语义锚点"
        )

        full_context = "\n".join(
            [
                "【语义锚点识别结果】",
                anchor_context,
                "",
                "【Top-k 知识图谱证据链】",
                evidence_context,
            ]
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
                full_context
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
                method="kg_rag",
                candidate_disease=(
                    cleaned_disease
                ),
                user_observation=(
                    cleaned_observation
                ),
                llm_result=llm_result,
            )
        )

        return enforce_kg_rag_boundary(
            result=structured_result,
            ranked_paths=ranked_paths,
            anchor_count=len(anchors),
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "运行皮肤病辅助解释的 KG-RAG 方法。"
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
        help="返回的图谱证据链数量，默认 5",
    )

    parser.add_argument(
        "--max-hops",
        type=int,
        choices=[1, 2],
        default=2,
        help="图谱最大路径跳数，默认 2",
    )

    args = parser.parse_args()

    try:
        pipeline = KGRAGPipeline()

        result = pipeline.run(
            case_id=args.case_id,
            candidate_disease=(
                args.disease
            ),
            user_observation=(
                args.observation
            ),
            top_k=args.top_k,
            max_hops=args.max_hops,
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