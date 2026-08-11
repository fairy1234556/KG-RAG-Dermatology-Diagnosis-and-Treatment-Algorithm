"""
Build a reproducible evidence snapshot for Task 5.

The snapshot stores, for every fixed case:

1. Ordinary RAG Top-k text documents.
2. KG-RAG semantic anchors.
3. KG-RAG Top-k ranked evidence paths.
4. Hashes of the retrieval data and configuration files.

This script does not call the LLM API.

Run:

    python experiments/build_task5_evidence_snapshot.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from kg.path_ranker import EvidencePathRanker
from rag.text_retriever import BM25TextRetriever


DEFAULT_CASE_FILE = (
    PROJECT_ROOT
    / "experiments"
    / "cases"
    / "task4_cases_v1.json"
)

DEFAULT_OUTPUT_FILE = (
    PROJECT_ROOT
    / "experiments"
    / "results"
    / "task5_evidence_snapshot_v1"
    / "evidence_snapshot.json"
)

SOURCE_FILES = {
    "entity_nodes": (
        PROJECT_ROOT
        / "kg"
        / "csv"
        / "entity_nodes.csv"
    ),
    "triples": (
        PROJECT_ROOT
        / "kg"
        / "csv"
        / "triples.csv"
    ),
    "entity_aliases": (
        PROJECT_ROOT
        / "kg"
        / "csv"
        / "entity_aliases.csv"
    ),
    "rag_corpus": (
        PROJECT_ROOT
        / "rag"
        / "data"
        / "evidence_corpus_v1.jsonl"
    ),
    "relation_weights": (
        PROJECT_ROOT
        / "configs"
        / "relation_weights.yaml"
    ),
    "text_retriever_code": (
        PROJECT_ROOT
        / "rag"
        / "text_retriever.py"
    ),
    "path_retriever_code": (
        PROJECT_ROOT
        / "kg"
        / "path_retriever.py"
    ),
    "path_ranker_code": (
        PROJECT_ROOT
        / "kg"
        / "path_ranker.py"
    ),
}


def current_time() -> str:
    """返回带时区的当前时间。"""

    return (
        datetime.now()
        .astimezone()
        .isoformat(
            timespec="seconds"
        )
    )


def resolve_path(path: Path) -> Path:
    """将相对路径解析为项目目录下的绝对路径。"""

    if path.is_absolute():
        return path

    return PROJECT_ROOT / path


def load_json(
    file_path: Path,
) -> Dict[str, Any]:
    """读取 JSON 对象。"""

    if not file_path.exists():
        raise FileNotFoundError(
            f"找不到文件：{file_path}"
        )

    with file_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        payload = json.load(file)

    if not isinstance(payload, dict):
        raise ValueError(
            f"JSON 根节点必须是对象：{file_path}"
        )

    return payload


def write_json(
    payload: Dict[str, Any],
    file_path: Path,
) -> None:
    """原子方式写入 JSON。"""

    file_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_file = file_path.with_suffix(
        file_path.suffix + ".tmp"
    )

    with temporary_file.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            payload,
            file,
            ensure_ascii=False,
            indent=2,
        )

        file.write("\n")

    temporary_file.replace(
        file_path
    )


def calculate_sha256(
    file_path: Path,
) -> str:
    """计算文件 SHA256。"""

    if not file_path.exists():
        return ""

    digest = hashlib.sha256()

    with file_path.open(
        "rb",
    ) as file:
        while True:
            chunk = file.read(
                8192
            )

            if not chunk:
                break

            digest.update(
                chunk
            )

    return digest.hexdigest()


def serialize_rag_document(
    document: Any,
) -> Dict[str, Any]:
    """序列化普通 RAG 文本检索结果。"""

    return {
        "rank": int(
            document.rank
        ),
        "document_id": str(
            document.document_id
        ),
        "text": str(
            document.text
        ),
        "score": float(
            document.score
        ),
        "bm25_score": float(
            document.bm25_score
        ),
        "phrase_overlap_score": float(
            document.phrase_overlap_score
        ),
        "matched_terms": list(
            document.matched_terms
        ),
        "source_names": list(
            document.source_names
        ),
        "origin_record_ids": list(
            document.origin_record_ids
        ),
    }


def serialize_anchor(
    anchor: Any,
) -> Dict[str, Any]:
    """序列化语义锚点。"""

    return {
        "matched_text": str(
            anchor.matched_text
        ),
        "entity_id": str(
            anchor.entity_id
        ),
        "entity_name": str(
            anchor.entity_name
        ),
        "confidence": float(
            anchor.confidence
        ),
    }


def serialize_edge(
    edge: Any,
) -> Dict[str, Any]:
    """序列化知识图谱中的单条边。"""

    return {
        "triple_id": str(
            getattr(
                edge,
                "triple_id",
                "",
            )
        ),
        "head_name": str(
            getattr(
                edge,
                "head_name",
                "",
            )
        ),
        "relation_cn": str(
            getattr(
                edge,
                "relation_cn",
                "",
            )
        ),
        "tail_name": str(
            getattr(
                edge,
                "tail_name",
                "",
            )
        ),
        "evidence_text": str(
            getattr(
                edge,
                "evidence_text",
                "",
            )
        ),
    }


def build_path_text(
    edges: List[Dict[str, Any]],
) -> str:
    """生成可读的图谱路径字符串。"""

    path_parts: List[str] = []

    for index, edge in enumerate(
        edges
    ):
        if index == 0:
            path_parts.append(
                edge["head_name"]
            )

        path_parts.append(
            edge["relation_cn"]
        )

        path_parts.append(
            edge["tail_name"]
        )

    return " → ".join(
        path_parts
    )


def serialize_ranked_path(
    ranked_path: Any,
) -> Dict[str, Any]:
    """序列化排序后的知识图谱证据链。"""

    edges = [
        serialize_edge(edge)
        for edge in ranked_path.path.edges
    ]

    return {
        "rank": int(
            ranked_path.rank
        ),
        "path_id": str(
            ranked_path.path_id
        ),
        "path_text": build_path_text(
            edges
        ),
        "hop_count": int(
            ranked_path.hop_count
        ),
        "start_disease_name": str(
            ranked_path.start_disease_name
        ),
        "end_entity_id": str(
            ranked_path.end_entity_id
        ),
        "end_entity_name": str(
            ranked_path.end_entity_name
        ),
        "matched_anchor_names": list(
            ranked_path.matched_anchor_names
        ),
        "evidence_texts": list(
            ranked_path.evidence_texts
        ),
        "source_names": list(
            ranked_path.source_names
        ),
        "total_score": float(
            ranked_path.total_score
        ),
        "entity_match_score": float(
            ranked_path.entity_match_score
        ),
        "relation_weight_score": float(
            ranked_path.relation_weight_score
        ),
        "disease_match_score": float(
            ranked_path.disease_match_score
        ),
        "path_length_penalty": float(
            ranked_path.path_length_penalty
        ),
        "edges": edges,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "构建任务五证据一致性评价使用的"
            "固定检索证据快照。"
        )
    )

    parser.add_argument(
        "--case-file",
        type=Path,
        default=DEFAULT_CASE_FILE,
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_FILE,
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
    )

    parser.add_argument(
        "--max-hops",
        type=int,
        choices=[1, 2],
        default=2,
    )

    args = parser.parse_args()

    if args.top_k <= 0:
        parser.error(
            "--top-k 必须大于 0。"
        )

    case_file = resolve_path(
        args.case_file
    )

    output_file = resolve_path(
        args.output
    )

    try:
        dataset = load_json(
            case_file
        )

        cases = dataset.get(
            "cases",
            [],
        )

        if not isinstance(
            cases,
            list,
        ):
            raise ValueError(
                "病例集中的 cases 必须是数组。"
            )

        if not cases:
            raise ValueError(
                "病例集不能为空。"
            )

        text_retriever = (
            BM25TextRetriever()
        )

        path_ranker = (
            EvidencePathRanker()
        )

        snapshot_cases: List[
            Dict[str, Any]
        ] = []

        for index, case in enumerate(
            cases,
            start=1,
        ):
            if not isinstance(
                case,
                dict,
            ):
                raise ValueError(
                    f"第 {index} 个病例不是对象。"
                )

            case_id = str(
                case.get(
                    "case_id",
                    "",
                )
            ).strip()

            disease = str(
                case.get(
                    "candidate_disease",
                    "",
                )
            ).strip()

            observation = str(
                case.get(
                    "user_observation",
                    "",
                )
            ).strip()

            if not case_id:
                raise ValueError(
                    f"第 {index} 个病例 case_id 为空。"
                )

            print(
                f"[{index}/{len(cases)}] "
                f"正在冻结证据：{case_id}"
            )

            rag_documents = (
                text_retriever.retrieve(
                    candidate_disease=(
                        disease
                    ),
                    user_observation=(
                        observation
                    ),
                    top_k=args.top_k,
                )
            )

            (
                anchors,
                ranked_paths,
                retrieved_path_count,
            ) = path_ranker.rank(
                disease_query=disease,
                observation_text=(
                    observation
                ),
                top_k=args.top_k,
                max_hops=args.max_hops,
            )

            if not rag_documents:
                raise ValueError(
                    f"{case_id} 的普通 RAG "
                    "没有检索到证据。"
                )

            if not ranked_paths:
                raise ValueError(
                    f"{case_id} 的 KG-RAG "
                    "没有检索到证据链。"
                )

            snapshot_cases.append(
                {
                    "case_id": case_id,
                    "candidate_disease": (
                        disease
                    ),
                    "user_observation": (
                        observation
                    ),
                    "expected_concepts": (
                        case.get(
                            "expected_concepts",
                            [],
                        )
                    ),
                    "rag": {
                        "retrieval_method": (
                            "bm25_with_phrase_overlap"
                        ),
                        "retrieved_count": len(
                            rag_documents
                        ),
                        "documents": [
                            serialize_rag_document(
                                document
                            )
                            for document
                            in rag_documents
                        ],
                    },
                    "kg_rag": {
                        "anchor_count": len(
                            anchors
                        ),
                        "anchors": [
                            serialize_anchor(
                                anchor
                            )
                            for anchor in anchors
                        ],
                        "retrieved_path_count": (
                            retrieved_path_count
                        ),
                        "ranked_path_count": len(
                            ranked_paths
                        ),
                        "ranked_paths": [
                            serialize_ranked_path(
                                ranked_path
                            )
                            for ranked_path
                            in ranked_paths
                        ],
                    },
                }
            )

    except (
        FileNotFoundError,
        ValueError,
        TypeError,
        json.JSONDecodeError,
    ) as exc:
        print(
            f"任务五证据快照构建失败：{exc}"
        )
        return 1

    source_hashes = {
        name: {
            "path": str(
                file_path.relative_to(
                    PROJECT_ROOT
                )
            ),
            "exists": (
                file_path.exists()
            ),
            "sha256": (
                calculate_sha256(
                    file_path
                )
            ),
        }
        for name, file_path
        in SOURCE_FILES.items()
    }

    payload = {
        "snapshot_name": (
            "task5_evidence_snapshot_v1"
        ),
        "snapshot_version": "1.0",
        "generated_at": (
            current_time()
        ),
        "dataset_name": dataset.get(
            "dataset_name",
            "",
        ),
        "dataset_version": dataset.get(
            "dataset_version",
            "",
        ),
        "case_count": len(
            snapshot_cases
        ),
        "settings": {
            "rag_top_k": args.top_k,
            "kg_rag_top_k": args.top_k,
            "kg_rag_max_hops": (
                args.max_hops
            ),
        },
        "source_hashes": (
            source_hashes
        ),
        "cases": snapshot_cases,
    }

    write_json(
        payload,
        output_file,
    )

    total_rag_documents = sum(
        case["rag"]["retrieved_count"]
        for case in snapshot_cases
    )

    total_ranked_paths = sum(
        case["kg_rag"][
            "ranked_path_count"
        ]
        for case in snapshot_cases
    )

    total_anchors = sum(
        case["kg_rag"]["anchor_count"]
        for case in snapshot_cases
    )

    print("=" * 70)
    print("任务五证据快照构建完成")
    print("=" * 70)
    print(
        f"病例数量：{len(snapshot_cases)}"
    )
    print(
        "普通 RAG 文档数量："
        f"{total_rag_documents}"
    )
    print(
        "KG-RAG 语义锚点数量："
        f"{total_anchors}"
    )
    print(
        "KG-RAG Top-k 路径数量："
        f"{total_ranked_paths}"
    )
    print(
        f"输出文件：{output_file}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())