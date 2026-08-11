"""
Generate candidate evidence for Task 5 claim-level consistency checking.

The prefilter uses transparent lexical and metadata-based rules.

It does not call the LLM API.

For every primary core claim:

- pure LLM: no external evidence;
- ordinary RAG: rank retrieved text documents;
- KG-RAG: rank knowledge graph evidence paths.

Run:

    python experiments/prefilter_task5_claim_evidence.py
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Set


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_CLAIM_DATASET = (
    PROJECT_ROOT
    / "experiments"
    / "results"
    / "task5_claims_v1"
    / "task5_claim_dataset.json"
)

DEFAULT_EVIDENCE_SNAPSHOT = (
    PROJECT_ROOT
    / "experiments"
    / "results"
    / "task5_evidence_snapshot_v1"
    / "evidence_snapshot.json"
)

DEFAULT_OUTPUT_DIRECTORY = (
    PROJECT_ROOT
    / "experiments"
    / "results"
    / "task5_prefilter_v1"
)

METHOD_ORDER = [
    "llm",
    "rag",
    "kg_rag",
]

PREFILTER_VERSION = "1.0"

DEFAULT_TOP_N = 3

SCORE_WEIGHTS = {
    "token_recall": 0.40,
    "token_jaccard": 0.20,
    "character_bigram_recall": 0.20,
}

SCORE_BONUSES = {
    "reference_match": 0.25,
    "source_match": 0.10,
    "entity_match": 0.20,
    "disease_match": 0.10,
    "relation_match": 0.05,
}

DISEASE_ALIASES = {
    "良性角化性病变": [
        "良性角化性病变",
        "良性角化样病变",
        "良性角化病变",
    ],
    "血管性病变": [
        "血管性病变",
        "血管性皮损",
        "血管病变",
        "血管性皮肤病变",
    ],
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
    """将相对路径转换为项目根目录下的绝对路径。"""

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
    """原子写入 JSON 文件。"""

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


def write_csv(
    rows: List[Dict[str, Any]],
    file_path: Path,
) -> None:
    """写入 UTF-8 BOM CSV。"""

    if not rows:
        raise ValueError(
            "没有可写入 CSV 的预筛选结果。"
        )

    file_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = list(
        rows[0].keys()
    )

    with file_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(rows)


def normalize_text(text: str) -> str:
    """统一文本格式，用于词法匹配。"""

    normalized = str(
        text or ""
    ).lower()

    normalized = re.sub(
        r"[\s，。；、,.!?！？:：;"
        r"（）()【】\[\]{}"
        r"\"'“”‘’\-_/→]+",
        "",
        normalized,
    )

    return normalized


def unique_non_empty(
    values: Iterable[str],
) -> List[str]:
    """保留顺序，去除空值和重复值。"""

    result: List[str] = []

    for value in values:
        cleaned = str(
            value or ""
        ).strip()

        if (
            cleaned
            and cleaned not in result
        ):
            result.append(
                cleaned
            )

    return result


def tokenize(text: str) -> Set[str]:
    """
    对中英文文本进行轻量分词。

    中文使用单字和相邻双字；
    英文及数字使用连续词元。
    """

    normalized = str(
        text or ""
    ).lower()

    tokens: List[str] = []

    chinese_segments = re.findall(
        r"[\u4e00-\u9fff]+",
        normalized,
    )

    for segment in chinese_segments:
        characters = list(
            segment
        )

        tokens.extend(
            characters
        )

        tokens.extend(
            segment[index:index + 2]
            for index in range(
                len(segment) - 1
            )
        )

    latin_tokens = re.findall(
        r"[a-z0-9]+(?:[-_][a-z0-9]+)*",
        normalized,
    )

    tokens.extend(
        latin_tokens
    )

    return {
        token
        for token in tokens
        if token
    }


def character_bigrams(
    text: str,
) -> Set[str]:
    """生成归一化文本的相邻双字符集合。"""

    normalized = normalize_text(
        text
    )

    if len(normalized) < 2:
        return (
            {normalized}
            if normalized
            else set()
        )

    return {
        normalized[index:index + 2]
        for index in range(
            len(normalized) - 1
        )
    }


def safe_ratio(
    numerator: float,
    denominator: float,
) -> float:
    """安全计算比例。"""

    if denominator <= 0:
        return 0.0

    return numerator / denominator


def get_disease_forms(
    candidate_disease: str,
) -> List[str]:
    """取得候选疾病及其标准化同义名称。"""

    configured = DISEASE_ALIASES.get(
        candidate_disease,
        [],
    )

    return unique_non_empty(
        [candidate_disease] + configured
    )


def build_snapshot_mapping(
    snapshot: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """按 case_id 建立证据快照索引。"""

    cases = snapshot.get(
        "cases",
        [],
    )

    if not isinstance(cases, list):
        raise ValueError(
            "证据快照中的 cases 必须是数组。"
        )

    mapping: Dict[
        str,
        Dict[str, Any],
    ] = {}

    for case in cases:
        if not isinstance(case, dict):
            continue

        case_id = str(
            case.get(
                "case_id",
                "",
            )
        ).strip()

        if not case_id:
            continue

        if case_id in mapping:
            raise ValueError(
                f"证据快照存在重复病例：{case_id}"
            )

        mapping[case_id] = case

    return mapping


def build_rag_candidates(
    snapshot_case: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """从普通 RAG 快照构造候选证据。"""

    rag_data = snapshot_case.get(
        "rag",
        {},
    )

    documents = (
        rag_data.get(
            "documents",
            [],
        )
        if isinstance(rag_data, dict)
        else []
    )

    if not isinstance(documents, list):
        return []

    candidates: List[
        Dict[str, Any]
    ] = []

    for document in documents:
        if not isinstance(
            document,
            dict,
        ):
            continue

        candidates.append(
            {
                "evidence_ref": str(
                    document.get(
                        "document_id",
                        "",
                    )
                ).strip(),
                "evidence_type": (
                    "retrieved_text_document"
                ),
                "original_rank": int(
                    document.get(
                        "rank",
                        0,
                    )
                    or 0
                ),
                "evidence_text": str(
                    document.get(
                        "text",
                        "",
                    )
                ).strip(),
                "source_names": (
                    unique_non_empty(
                        document.get(
                            "source_names",
                            [],
                        )
                        if isinstance(
                            document.get(
                                "source_names",
                                [],
                            ),
                            list,
                        )
                        else []
                    )
                ),
                "entity_phrases": [],
                "relation_phrases": [],
                "retrieval_score": float(
                    document.get(
                        "score",
                        0.0,
                    )
                    or 0.0
                ),
            }
        )

    return candidates


def build_kg_rag_candidates(
    snapshot_case: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """从 KG-RAG 快照构造候选图谱证据链。"""

    kg_data = snapshot_case.get(
        "kg_rag",
        {},
    )

    ranked_paths = (
        kg_data.get(
            "ranked_paths",
            [],
        )
        if isinstance(kg_data, dict)
        else []
    )

    if not isinstance(
        ranked_paths,
        list,
    ):
        return []

    candidates: List[
        Dict[str, Any]
    ] = []

    for path in ranked_paths:
        if not isinstance(
            path,
            dict,
        ):
            continue

        evidence_texts = path.get(
            "evidence_texts",
            [],
        )

        if not isinstance(
            evidence_texts,
            list,
        ):
            evidence_texts = []

        edges = path.get(
            "edges",
            [],
        )

        if not isinstance(edges, list):
            edges = []

        entity_phrases: List[str] = [
            str(
                path.get(
                    "end_entity_name",
                    "",
                )
            )
        ]

        relation_phrases: List[str] = []

        for edge in edges:
            if not isinstance(
                edge,
                dict,
            ):
                continue

            entity_phrases.extend(
                [
                    str(
                        edge.get(
                            "tail_name",
                            "",
                        )
                    ),
                    str(
                        edge.get(
                            "head_name",
                            "",
                        )
                    ),
                ]
            )

            relation_phrases.append(
                str(
                    edge.get(
                        "relation_cn",
                        "",
                    )
                )
            )

        path_text = str(
            path.get(
                "path_text",
                "",
            )
        ).strip()

        combined_evidence_text = "\n".join(
            unique_non_empty(
                [path_text]
                + [
                    str(text)
                    for text in evidence_texts
                ]
            )
        )

        candidates.append(
            {
                "evidence_ref": str(
                    path.get(
                        "path_id",
                        "",
                    )
                ).strip(),
                "evidence_type": (
                    "ranked_kg_evidence_path"
                ),
                "original_rank": int(
                    path.get(
                        "rank",
                        0,
                    )
                    or 0
                ),
                "evidence_text": (
                    combined_evidence_text
                ),
                "source_names": (
                    unique_non_empty(
                        path.get(
                            "source_names",
                            [],
                        )
                        if isinstance(
                            path.get(
                                "source_names",
                                [],
                            ),
                            list,
                        )
                        else []
                    )
                ),
                "entity_phrases": (
                    unique_non_empty(
                        entity_phrases
                    )
                ),
                "relation_phrases": (
                    unique_non_empty(
                        relation_phrases
                    )
                ),
                "retrieval_score": float(
                    path.get(
                        "total_score",
                        0.0,
                    )
                    or 0.0
                ),
            }
        )

    return candidates


def build_candidates(
    method_name: str,
    snapshot_case: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """根据方法取得允许使用的候选证据。"""

    if method_name == "llm":
        return []

    if method_name == "rag":
        return build_rag_candidates(
            snapshot_case
        )

    if method_name == "kg_rag":
        return build_kg_rag_candidates(
            snapshot_case
        )

    raise ValueError(
        f"未知方法：{method_name}"
    )


def contains_any_phrase(
    text: str,
    phrases: Sequence[str],
) -> bool:
    """检查文本中是否包含任一有效短语。"""

    normalized_text = normalize_text(
        text
    )

    for phrase in phrases:
        normalized_phrase = normalize_text(
            phrase
        )

        if (
            len(normalized_phrase) >= 2
            and normalized_phrase
            in normalized_text
        ):
            return True

    return False


def score_candidate(
    claim_text: str,
    candidate_disease: str,
    candidate: Dict[str, Any],
) -> Dict[str, Any]:
    """计算单条陈述与一条候选证据的匹配分。"""

    evidence_text = str(
        candidate.get(
            "evidence_text",
            "",
        )
    )

    claim_tokens = tokenize(
        claim_text
    )

    evidence_tokens = tokenize(
        evidence_text
    )

    token_intersection = (
        claim_tokens
        & evidence_tokens
    )

    token_recall = safe_ratio(
        len(token_intersection),
        len(claim_tokens),
    )

    token_union = (
        claim_tokens
        | evidence_tokens
    )

    token_jaccard = safe_ratio(
        len(token_intersection),
        len(token_union),
    )

    claim_bigrams = (
        character_bigrams(
            claim_text
        )
    )

    evidence_bigrams = (
        character_bigrams(
            evidence_text
        )
    )

    bigram_intersection = (
        claim_bigrams
        & evidence_bigrams
    )

    character_bigram_recall = safe_ratio(
        len(bigram_intersection),
        len(claim_bigrams),
    )

    evidence_ref = str(
        candidate.get(
            "evidence_ref",
            "",
        )
    )

    reference_match = bool(
        evidence_ref
        and normalize_text(
            evidence_ref
        )
        in normalize_text(
            claim_text
        )
    )

    source_match = contains_any_phrase(
        claim_text,
        candidate.get(
            "source_names",
            [],
        ),
    )

    entity_match = contains_any_phrase(
        claim_text,
        candidate.get(
            "entity_phrases",
            [],
        ),
    )

    relation_match = contains_any_phrase(
        claim_text,
        candidate.get(
            "relation_phrases",
            [],
        ),
    )

    disease_forms = get_disease_forms(
        candidate_disease
    )

    disease_match = (
        contains_any_phrase(
            claim_text,
            disease_forms,
        )
        and contains_any_phrase(
            evidence_text,
            disease_forms,
        )
    )

    lexical_score = (
        SCORE_WEIGHTS[
            "token_recall"
        ]
        * token_recall
        + SCORE_WEIGHTS[
            "token_jaccard"
        ]
        * token_jaccard
        + SCORE_WEIGHTS[
            "character_bigram_recall"
        ]
        * character_bigram_recall
    )

    bonus_score = (
        SCORE_BONUSES[
            "reference_match"
        ]
        * int(reference_match)
        + SCORE_BONUSES[
            "source_match"
        ]
        * int(source_match)
        + SCORE_BONUSES[
            "entity_match"
        ]
        * int(entity_match)
        + SCORE_BONUSES[
            "disease_match"
        ]
        * int(disease_match)
        + SCORE_BONUSES[
            "relation_match"
        ]
        * int(relation_match)
    )

    total_score = min(
        1.0,
        lexical_score
        + bonus_score,
    )

    if total_score >= 0.55:
        quality = "strong"

    elif total_score >= 0.30:
        quality = "moderate"

    elif total_score > 0:
        quality = "weak"

    else:
        quality = "none"

    return {
        "score": round(
            total_score,
            6,
        ),
        "quality": quality,
        "token_recall": round(
            token_recall,
            6,
        ),
        "token_jaccard": round(
            token_jaccard,
            6,
        ),
        "character_bigram_recall": round(
            character_bigram_recall,
            6,
        ),
        "reference_match": (
            reference_match
        ),
        "source_match": (
            source_match
        ),
        "entity_match": (
            entity_match
        ),
        "disease_match": (
            disease_match
        ),
        "relation_match": (
            relation_match
        ),
        "matched_tokens": sorted(
            token_intersection
        ),
    }


def process_claim(
    claim: Dict[str, Any],
    candidate_disease: str,
    evidence_candidates: List[
        Dict[str, Any]
    ],
    top_n: int,
) -> Dict[str, Any]:
    """为一条生成陈述生成候选支持证据。"""

    method_name = str(
        claim.get(
            "method",
            "",
        )
    )

    is_duplicate = bool(
        claim.get(
            "is_duplicate",
            False,
        )
    )

    included_in_core = bool(
        claim.get(
            "included_in_core_consistency",
            False,
        )
    )

    record = {
        "claim_id": str(
            claim.get(
                "claim_id",
                "",
            )
        ),
        "case_id": str(
            claim.get(
                "case_id",
                "",
            )
        ),
        "method": method_name,
        "source_field": str(
            claim.get(
                "source_field",
                "",
            )
        ),
        "claim_type": str(
            claim.get(
                "claim_type",
                "",
            )
        ),
        "claim_type_cn": str(
            claim.get(
                "claim_type_cn",
                "",
            )
        ),
        "claim_text": str(
            claim.get(
                "claim_text",
                "",
            )
        ),
        "is_duplicate": (
            is_duplicate
        ),
        "included_in_core_consistency": (
            included_in_core
        ),
        "prefilter_status": "",
        "candidate_count": 0,
        "top_candidate_score": None,
        "top_candidate_quality": "",
        "candidates": [],
    }

    if is_duplicate:
        record[
            "prefilter_status"
        ] = "duplicate_skipped"

        return record

    if not included_in_core:
        record[
            "prefilter_status"
        ] = "not_applicable"

        return record

    if method_name == "llm":
        record[
            "prefilter_status"
        ] = "no_external_evidence"

        return record

    scored_candidates: List[
        Dict[str, Any]
    ] = []

    for candidate in evidence_candidates:
        scoring = score_candidate(
            claim_text=record[
                "claim_text"
            ],
            candidate_disease=(
                candidate_disease
            ),
            candidate=candidate,
        )

        scored_candidates.append(
            {
                "evidence_ref": (
                    candidate[
                        "evidence_ref"
                    ]
                ),
                "evidence_type": (
                    candidate[
                        "evidence_type"
                    ]
                ),
                "original_rank": (
                    candidate[
                        "original_rank"
                    ]
                ),
                "evidence_text": (
                    candidate[
                        "evidence_text"
                    ]
                ),
                "source_names": (
                    candidate[
                        "source_names"
                    ]
                ),
                "retrieval_score": (
                    candidate[
                        "retrieval_score"
                    ]
                ),
                "prefilter_score": (
                    scoring["score"]
                ),
                "prefilter_quality": (
                    scoring["quality"]
                ),
                "score_components": (
                    scoring
                ),
            }
        )

    scored_candidates.sort(
        key=lambda item: (
            -item[
                "prefilter_score"
            ],
            item[
                "original_rank"
            ],
            item[
                "evidence_ref"
            ],
        )
    )

    selected_candidates = (
        scored_candidates[
            :top_n
        ]
    )

    for rank, candidate in enumerate(
        selected_candidates,
        start=1,
    ):
        candidate[
            "candidate_rank"
        ] = rank

    record[
        "prefilter_status"
    ] = (
        "candidate_generated"
        if selected_candidates
        else "no_candidate_evidence"
    )

    record[
        "candidate_count"
    ] = len(
        selected_candidates
    )

    record[
        "candidates"
    ] = (
        selected_candidates
    )

    if selected_candidates:
        record[
            "top_candidate_score"
        ] = selected_candidates[
            0
        ][
            "prefilter_score"
        ]

        record[
            "top_candidate_quality"
        ] = selected_candidates[
            0
        ][
            "prefilter_quality"
        ]

    return record


def build_csv_rows(
    records: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """展开为一行一个陈述—候选证据组合。"""

    rows: List[
        Dict[str, Any]
    ] = []

    for record in records:
        candidates = record.get(
            "candidates",
            [],
        )

        if not candidates:
            rows.append(
                {
                    "claim_id": record[
                        "claim_id"
                    ],
                    "case_id": record[
                        "case_id"
                    ],
                    "method": record[
                        "method"
                    ],
                    "source_field": record[
                        "source_field"
                    ],
                    "claim_type_cn": record[
                        "claim_type_cn"
                    ],
                    "claim_text": record[
                        "claim_text"
                    ],
                    "prefilter_status": record[
                        "prefilter_status"
                    ],
                    "candidate_rank": "",
                    "evidence_ref": "",
                    "evidence_type": "",
                    "evidence_text": "",
                    "source_names": "",
                    "retrieval_score": "",
                    "prefilter_score": "",
                    "prefilter_quality": "",
                    "token_recall": "",
                    "token_jaccard": "",
                    "character_bigram_recall": "",
                    "reference_match": "",
                    "source_match": "",
                    "entity_match": "",
                    "disease_match": "",
                    "relation_match": "",
                }
            )

            continue

        for candidate in candidates:
            components = candidate[
                "score_components"
            ]

            rows.append(
                {
                    "claim_id": record[
                        "claim_id"
                    ],
                    "case_id": record[
                        "case_id"
                    ],
                    "method": record[
                        "method"
                    ],
                    "source_field": record[
                        "source_field"
                    ],
                    "claim_type_cn": record[
                        "claim_type_cn"
                    ],
                    "claim_text": record[
                        "claim_text"
                    ],
                    "prefilter_status": record[
                        "prefilter_status"
                    ],
                    "candidate_rank": (
                        candidate[
                            "candidate_rank"
                        ]
                    ),
                    "evidence_ref": (
                        candidate[
                            "evidence_ref"
                        ]
                    ),
                    "evidence_type": (
                        candidate[
                            "evidence_type"
                        ]
                    ),
                    "evidence_text": (
                        candidate[
                            "evidence_text"
                        ]
                    ),
                    "source_names": (
                        "；".join(
                            candidate[
                                "source_names"
                            ]
                        )
                    ),
                    "retrieval_score": (
                        candidate[
                            "retrieval_score"
                        ]
                    ),
                    "prefilter_score": (
                        candidate[
                            "prefilter_score"
                        ]
                    ),
                    "prefilter_quality": (
                        candidate[
                            "prefilter_quality"
                        ]
                    ),
                    "token_recall": (
                        components[
                            "token_recall"
                        ]
                    ),
                    "token_jaccard": (
                        components[
                            "token_jaccard"
                        ]
                    ),
                    "character_bigram_recall": (
                        components[
                            "character_bigram_recall"
                        ]
                    ),
                    "reference_match": (
                        components[
                            "reference_match"
                        ]
                    ),
                    "source_match": (
                        components[
                            "source_match"
                        ]
                    ),
                    "entity_match": (
                        components[
                            "entity_match"
                        ]
                    ),
                    "disease_match": (
                        components[
                            "disease_match"
                        ]
                    ),
                    "relation_match": (
                        components[
                            "relation_match"
                        ]
                    ),
                }
            )

    return rows


def calculate_summary(
    records: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """计算规则预筛选摘要。"""

    method_summary: Dict[
        str,
        Dict[str, Any],
    ] = {}

    for method_name in METHOD_ORDER:
        method_records = [
            record
            for record in records
            if record["method"]
            == method_name
        ]

        core_records = [
            record
            for record in method_records
            if (
                record[
                    "included_in_core_consistency"
                ]
                and not record[
                    "is_duplicate"
                ]
            )
        ]

        generated_records = [
            record
            for record in core_records
            if record[
                "prefilter_status"
            ]
            == "candidate_generated"
        ]

        strong_records = [
            record
            for record in generated_records
            if record[
                "top_candidate_quality"
            ]
            == "strong"
        ]

        moderate_records = [
            record
            for record in generated_records
            if record[
                "top_candidate_quality"
            ]
            == "moderate"
        ]

        weak_records = [
            record
            for record in generated_records
            if record[
                "top_candidate_quality"
            ]
            in {
                "weak",
                "none",
            }
        ]

        method_summary[
            method_name
        ] = {
            "claim_count": len(
                method_records
            ),
            "primary_core_claim_count": (
                len(core_records)
            ),
            "candidate_generated_count": (
                len(generated_records)
            ),
            "no_external_evidence_count": sum(
                1
                for record in core_records
                if record[
                    "prefilter_status"
                ]
                == "no_external_evidence"
            ),
            "strong_top_candidate_count": (
                len(strong_records)
            ),
            "moderate_top_candidate_count": (
                len(moderate_records)
            ),
            "weak_top_candidate_count": (
                len(weak_records)
            ),
        }

    return {
        "record_count": len(
            records
        ),
        "candidate_pair_count": sum(
            len(
                record.get(
                    "candidates",
                    [],
                )
            )
            for record in records
        ),
        "method_summary": (
            method_summary
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "为任务五逐条陈述生成候选支持证据。"
        )
    )

    parser.add_argument(
        "--claim-dataset",
        type=Path,
        default=DEFAULT_CLAIM_DATASET,
    )

    parser.add_argument(
        "--evidence-snapshot",
        type=Path,
        default=DEFAULT_EVIDENCE_SNAPSHOT,
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIRECTORY,
    )

    parser.add_argument(
        "--top-n",
        type=int,
        default=DEFAULT_TOP_N,
        help="每条陈述保留的候选证据数量",
    )

    args = parser.parse_args()

    if args.top_n <= 0:
        parser.error(
            "--top-n 必须大于 0。"
        )

    claim_dataset_file = resolve_path(
        args.claim_dataset
    )

    evidence_snapshot_file = (
        resolve_path(
            args.evidence_snapshot
        )
    )

    output_directory = resolve_path(
        args.output_dir
    )

    try:
        claim_dataset = load_json(
            claim_dataset_file
        )

        evidence_snapshot = load_json(
            evidence_snapshot_file
        )

        snapshot_mapping = (
            build_snapshot_mapping(
                evidence_snapshot
            )
        )

        cases = claim_dataset.get(
            "cases",
            [],
        )

        if not isinstance(cases, list):
            raise ValueError(
                "陈述数据集中的 cases 必须是数组。"
            )

        records: List[
            Dict[str, Any]
        ] = []

        structured_cases: List[
            Dict[str, Any]
        ] = []

        for case_index, case in enumerate(
            cases,
            start=1,
        ):
            if not isinstance(
                case,
                dict,
            ):
                raise ValueError(
                    f"第 {case_index} 个病例不是对象。"
                )

            case_id = str(
                case.get(
                    "case_id",
                    "",
                )
            ).strip()

            candidate_disease = str(
                case.get(
                    "candidate_disease",
                    "",
                )
            ).strip()

            if case_id not in snapshot_mapping:
                raise ValueError(
                    f"证据快照缺少病例：{case_id}"
                )

            snapshot_case = (
                snapshot_mapping[
                    case_id
                ]
            )

            method_outputs: List[
                Dict[str, Any]
            ] = []

            print(
                f"[{case_index}/{len(cases)}] "
                f"正在生成候选证据：{case_id}"
            )

            methods = case.get(
                "methods",
                [],
            )

            if not isinstance(
                methods,
                list,
            ):
                raise ValueError(
                    f"{case_id} 的 methods 必须是数组。"
                )

            method_mapping = {
                str(
                    method.get(
                        "method",
                        "",
                    )
                ): method
                for method in methods
                if isinstance(
                    method,
                    dict,
                )
            }

            for method_name in METHOD_ORDER:
                if method_name not in method_mapping:
                    raise ValueError(
                        f"{case_id} 缺少方法：{method_name}"
                    )

                method_data = (
                    method_mapping[
                        method_name
                    ]
                )

                claims = method_data.get(
                    "claims",
                    [],
                )

                if not isinstance(
                    claims,
                    list,
                ):
                    raise ValueError(
                        f"{case_id} 的 {method_name} "
                        "claims 必须是数组。"
                    )

                evidence_candidates = (
                    build_candidates(
                        method_name=(
                            method_name
                        ),
                        snapshot_case=(
                            snapshot_case
                        ),
                    )
                )

                processed_claims = [
                    process_claim(
                        claim=claim,
                        candidate_disease=(
                            candidate_disease
                        ),
                        evidence_candidates=(
                            evidence_candidates
                        ),
                        top_n=args.top_n,
                    )
                    for claim in claims
                    if isinstance(
                        claim,
                        dict,
                    )
                ]

                records.extend(
                    processed_claims
                )

                method_outputs.append(
                    {
                        "method": (
                            method_name
                        ),
                        "evidence_candidate_pool_size": (
                            len(
                                evidence_candidates
                            )
                        ),
                        "claim_count": len(
                            processed_claims
                        ),
                        "claims": (
                            processed_claims
                        ),
                    }
                )

            structured_cases.append(
                {
                    "case_id": case_id,
                    "candidate_disease": (
                        candidate_disease
                    ),
                    "user_observation": str(
                        case.get(
                            "user_observation",
                            "",
                        )
                    ),
                    "methods": (
                        method_outputs
                    ),
                }
            )

    except (
        FileNotFoundError,
        ValueError,
        TypeError,
        json.JSONDecodeError,
    ) as exc:
        print(
            f"任务五规则预筛选失败：{exc}"
        )
        return 1

    summary = calculate_summary(
        records
    )

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_json = (
        output_directory
        / "task5_claim_evidence_candidates.json"
    )

    output_csv = (
        output_directory
        / "task5_claim_evidence_candidates.csv"
    )

    payload = {
        "dataset_name": (
            "task5_claim_evidence_prefilter_v1"
        ),
        "dataset_version": (
            PREFILTER_VERSION
        ),
        "generated_at": (
            current_time()
        ),
        "case_count": len(
            structured_cases
        ),
        "top_n": args.top_n,
        "scoring_configuration": {
            "weights": (
                SCORE_WEIGHTS
            ),
            "bonuses": (
                SCORE_BONUSES
            ),
            "quality_thresholds": {
                "strong": (
                    "score >= 0.55"
                ),
                "moderate": (
                    "0.30 <= score < 0.55"
                ),
                "weak": (
                    "0 < score < 0.30"
                ),
                "none": (
                    "score = 0"
                ),
            },
        },
        "summary": summary,
        "cases": structured_cases,
    }

    write_json(
        payload=payload,
        file_path=output_json,
    )

    csv_rows = build_csv_rows(
        records
    )

    write_csv(
        rows=csv_rows,
        file_path=output_csv,
    )

    print("=" * 70)
    print("任务五规则预筛选完成")
    print("=" * 70)
    print(
        f"病例数量：{len(structured_cases)}"
    )
    print(
        f"陈述记录数量："
        f"{summary['record_count']}"
    )
    print(
        f"陈述—证据候选对数量："
        f"{summary['candidate_pair_count']}"
    )
    print("-" * 70)

    for method_name in METHOD_ORDER:
        method_summary = (
            summary[
                "method_summary"
            ][method_name]
        )

        print(
            f"{method_name} | "
            f"核心陈述="
            f"{method_summary['primary_core_claim_count']} | "
            f"生成候选="
            f"{method_summary['candidate_generated_count']} | "
            f"无外部证据="
            f"{method_summary['no_external_evidence_count']} | "
            f"强匹配="
            f"{method_summary['strong_top_candidate_count']} | "
            f"中等匹配="
            f"{method_summary['moderate_top_candidate_count']} | "
            f"弱匹配="
            f"{method_summary['weak_top_candidate_count']}"
        )

    print("-" * 70)
    print(
        f"JSON 结果：{output_json}"
    )
    print(
        f"CSV 结果：{output_csv}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())