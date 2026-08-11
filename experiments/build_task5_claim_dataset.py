"""
Build the claim-level dataset for Task 5 evidence consistency checking.

The script converts every structured model output item into one claim.

It does not call the LLM API.

Run:

    python experiments/build_task5_claim_dataset.py
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_CASE_FILE = (
    PROJECT_ROOT
    / "experiments"
    / "cases"
    / "task4_cases_v1.json"
)

DEFAULT_RESULT_DIRECTORY = (
    PROJECT_ROOT
    / "experiments"
    / "results"
    / "task4_batch_v1"
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
    / "task5_claims_v1"
)

METHOD_ORDER = [
    "llm",
    "rag",
    "kg_rag",
]

FIELD_ORDER = [
    "observation_match",
    "supporting_evidence",
    "differential_diagnosis",
    "risk_warning",
    "medical_advice",
    "evidence_gap",
]

FIELD_POLICY: Dict[str, Dict[str, Any]] = {
    "observation_match": {
        "claim_type": "observation_alignment",
        "claim_type_cn": "观察匹配陈述",
        "claim_scope": "core_consistency",
        "evidence_required": True,
        "included_in_core_consistency": True,
    },
    "supporting_evidence": {
        "claim_type": "supporting_medical_claim",
        "claim_type_cn": "支持性医学陈述",
        "claim_scope": "core_consistency",
        "evidence_required": True,
        "included_in_core_consistency": True,
    },
    "differential_diagnosis": {
        "claim_type": "differential_claim",
        "claim_type_cn": "鉴别诊断陈述",
        "claim_scope": "core_consistency",
        "evidence_required": True,
        "included_in_core_consistency": True,
    },
    "risk_warning": {
        "claim_type": "risk_claim",
        "claim_type_cn": "风险医学陈述",
        "claim_scope": "core_consistency",
        "evidence_required": True,
        "included_in_core_consistency": True,
    },
    "medical_advice": {
        "claim_type": "medical_advice",
        "claim_type_cn": "医疗建议",
        "claim_scope": "auxiliary_safety",
        "evidence_required": False,
        "included_in_core_consistency": False,
    },
    "evidence_gap": {
        "claim_type": "evidence_limitation",
        "claim_type_cn": "证据缺口说明",
        "claim_scope": "auxiliary_limitation",
        "evidence_required": False,
        "included_in_core_consistency": False,
    },
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
    """原子方式写入 JSON 文件。"""

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
    """写入 UTF-8 BOM CSV，便于 Excel 打开。"""

    if not rows:
        raise ValueError(
            "没有可写入 CSV 的逐条陈述。"
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


def calculate_sha256(
    file_path: Path,
) -> str:
    """计算文件 SHA256。"""

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


def ensure_string_list(
    value: Any,
) -> List[str]:
    """将模型字段安全转换为字符串数组。"""

    if value is None:
        return []

    if isinstance(value, str):
        cleaned = value.strip()
        return [cleaned] if cleaned else []

    if not isinstance(value, list):
        return []

    values: List[str] = []

    for item in value:
        if not isinstance(item, str):
            continue

        cleaned = item.strip()

        if cleaned:
            values.append(
                cleaned
            )

    return values


def unique_non_empty(
    values: Iterable[str],
) -> List[str]:
    """保留顺序并去除空值与重复值。"""

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


def normalize_claim_text(
    text: str,
) -> str:
    """生成用于检测完全重复陈述的文本签名。"""

    normalized = str(
        text or ""
    ).lower()

    normalized = re.sub(
        r"[\s，。；、,.!?！？:：;"
        r"（）()【】\[\]{}"
        r"\"'“”‘’\-_/]+",
        "",
        normalized,
    )

    return normalized


def find_method_record(
    experiment: Dict[str, Any],
    method_name: str,
) -> Dict[str, Any]:
    """从单病例实验文件中查找指定方法。"""

    records = experiment.get(
        "method_results",
        [],
    )

    if not isinstance(records, list):
        raise ValueError(
            "method_results 必须是数组。"
        )

    matched_records = [
        record
        for record in records
        if (
            isinstance(record, dict)
            and record.get("method")
            == method_name
        )
    ]

    if len(matched_records) != 1:
        raise ValueError(
            f"方法 {method_name} 的结果数量不为 1，"
            f"实际为 {len(matched_records)}。"
        )

    return matched_records[0]


def build_snapshot_mapping(
    snapshot: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """按 case_id 建立证据快照索引。"""

    snapshot_cases = snapshot.get(
        "cases",
        [],
    )

    if not isinstance(
        snapshot_cases,
        list,
    ):
        raise ValueError(
            "证据快照中的 cases 必须是数组。"
        )

    mapping: Dict[
        str,
        Dict[str, Any],
    ] = {}

    for snapshot_case in snapshot_cases:
        if not isinstance(
            snapshot_case,
            dict,
        ):
            continue

        case_id = str(
            snapshot_case.get(
                "case_id",
                "",
            )
        ).strip()

        if not case_id:
            continue

        if case_id in mapping:
            raise ValueError(
                f"证据快照存在重复 case_id：{case_id}"
            )

        mapping[case_id] = (
            snapshot_case
        )

    return mapping


def collect_rag_evidence(
    snapshot_case: Dict[str, Any],
) -> Dict[str, Any]:
    """取得普通 RAG 允许使用的证据范围。"""

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
        documents = []

    evidence_refs: List[str] = []
    source_names: List[str] = []

    for document in documents:
        if not isinstance(
            document,
            dict,
        ):
            continue

        document_id = str(
            document.get(
                "document_id",
                "",
            )
        ).strip()

        if document_id:
            evidence_refs.append(
                document_id
            )

        names = document.get(
            "source_names",
            [],
        )

        if isinstance(names, list):
            source_names.extend(
                str(name)
                for name in names
            )

    return {
        "allowed_evidence_type": (
            "retrieved_text_document"
        ),
        "allowed_evidence_count": len(
            evidence_refs
        ),
        "allowed_evidence_refs": (
            unique_non_empty(
                evidence_refs
            )
        ),
        "allowed_source_names": (
            unique_non_empty(
                source_names
            )
        ),
    }


def collect_kg_rag_evidence(
    snapshot_case: Dict[str, Any],
) -> Dict[str, Any]:
    """取得 KG-RAG 允许使用的证据范围。"""

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
        ranked_paths = []

    evidence_refs: List[str] = []
    source_names: List[str] = []

    for path in ranked_paths:
        if not isinstance(
            path,
            dict,
        ):
            continue

        path_id = str(
            path.get(
                "path_id",
                "",
            )
        ).strip()

        if path_id:
            evidence_refs.append(
                path_id
            )

        names = path.get(
            "source_names",
            [],
        )

        if isinstance(names, list):
            source_names.extend(
                str(name)
                for name in names
            )

    return {
        "allowed_evidence_type": (
            "ranked_kg_evidence_path"
        ),
        "allowed_evidence_count": len(
            evidence_refs
        ),
        "allowed_evidence_refs": (
            unique_non_empty(
                evidence_refs
            )
        ),
        "allowed_source_names": (
            unique_non_empty(
                source_names
            )
        ),
    }


def get_allowed_evidence(
    method_name: str,
    snapshot_case: Dict[str, Any],
) -> Dict[str, Any]:
    """根据实验方法确定本次允许使用的外部证据。"""

    if method_name == "llm":
        return {
            "allowed_evidence_type": (
                "none"
            ),
            "allowed_evidence_count": 0,
            "allowed_evidence_refs": [],
            "allowed_source_names": [],
        }

    if method_name == "rag":
        return collect_rag_evidence(
            snapshot_case
        )

    if method_name == "kg_rag":
        return collect_kg_rag_evidence(
            snapshot_case
        )

    raise ValueError(
        f"未知实验方法：{method_name}"
    )


def extract_claims(
    case_id: str,
    method_name: str,
    result: Dict[str, Any],
    evidence_scope: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """将结构化输出拆成逐条陈述。"""

    claims: List[
        Dict[str, Any]
    ] = []

    seen_signatures: Dict[
        str,
        str,
    ] = {}

    global_claim_index = 0

    output_sources = unique_non_empty(
        ensure_string_list(
            result.get(
                "sources",
                [],
            )
        )
    )

    for field_name in FIELD_ORDER:
        policy = FIELD_POLICY[
            field_name
        ]

        field_values = (
            ensure_string_list(
                result.get(
                    field_name,
                    [],
                )
            )
        )

        for field_index, claim_text in enumerate(
            field_values,
            start=1,
        ):
            global_claim_index += 1

            claim_id = (
                f"{case_id}__"
                f"{method_name}__"
                f"{field_name}__"
                f"{field_index:03d}"
            )

            signature = normalize_claim_text(
                claim_text
            )

            duplicate_of_claim_id = (
                seen_signatures.get(
                    signature,
                    "",
                )
            )

            is_duplicate = bool(
                duplicate_of_claim_id
            )

            if (
                signature
                and not is_duplicate
            ):
                seen_signatures[
                    signature
                ] = claim_id

            claims.append(
                {
                    "claim_id": claim_id,
                    "case_id": case_id,
                    "method": method_name,
                    "global_claim_index": (
                        global_claim_index
                    ),
                    "source_field": (
                        field_name
                    ),
                    "field_claim_index": (
                        field_index
                    ),
                    "claim_type": (
                        policy[
                            "claim_type"
                        ]
                    ),
                    "claim_type_cn": (
                        policy[
                            "claim_type_cn"
                        ]
                    ),
                    "claim_scope": (
                        policy[
                            "claim_scope"
                        ]
                    ),
                    "evidence_required": (
                        policy[
                            "evidence_required"
                        ]
                    ),
                    "included_in_core_consistency": (
                        policy[
                            "included_in_core_consistency"
                        ]
                    ),
                    "claim_text": (
                        claim_text
                    ),
                    "claim_text_signature": (
                        signature
                    ),
                    "is_duplicate": (
                        is_duplicate
                    ),
                    "duplicate_of_claim_id": (
                        duplicate_of_claim_id
                    ),
                    "allowed_evidence_type": (
                        evidence_scope[
                            "allowed_evidence_type"
                        ]
                    ),
                    "allowed_evidence_count": (
                        evidence_scope[
                            "allowed_evidence_count"
                        ]
                    ),
                    "allowed_evidence_refs": (
                        evidence_scope[
                            "allowed_evidence_refs"
                        ]
                    ),
                    "allowed_source_names": (
                        evidence_scope[
                            "allowed_source_names"
                        ]
                    ),
                    "output_sources": (
                        output_sources
                    ),
                }
            )

    return claims


def build_csv_rows(
    claims: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """将嵌套字段转换为 CSV 可写格式。"""

    rows: List[
        Dict[str, Any]
    ] = []

    for claim in claims:
        rows.append(
            {
                "claim_id": (
                    claim["claim_id"]
                ),
                "case_id": (
                    claim["case_id"]
                ),
                "method": (
                    claim["method"]
                ),
                "global_claim_index": (
                    claim[
                        "global_claim_index"
                    ]
                ),
                "source_field": (
                    claim["source_field"]
                ),
                "field_claim_index": (
                    claim[
                        "field_claim_index"
                    ]
                ),
                "claim_type": (
                    claim["claim_type"]
                ),
                "claim_type_cn": (
                    claim[
                        "claim_type_cn"
                    ]
                ),
                "claim_scope": (
                    claim["claim_scope"]
                ),
                "evidence_required": (
                    claim[
                        "evidence_required"
                    ]
                ),
                "included_in_core_consistency": (
                    claim[
                        "included_in_core_consistency"
                    ]
                ),
                "claim_text": (
                    claim["claim_text"]
                ),
                "is_duplicate": (
                    claim["is_duplicate"]
                ),
                "duplicate_of_claim_id": (
                    claim[
                        "duplicate_of_claim_id"
                    ]
                ),
                "allowed_evidence_type": (
                    claim[
                        "allowed_evidence_type"
                    ]
                ),
                "allowed_evidence_count": (
                    claim[
                        "allowed_evidence_count"
                    ]
                ),
                "allowed_evidence_refs": (
                    "；".join(
                        claim[
                            "allowed_evidence_refs"
                        ]
                    )
                ),
                "allowed_source_names": (
                    "；".join(
                        claim[
                            "allowed_source_names"
                        ]
                    )
                ),
                "output_sources": (
                    "；".join(
                        claim[
                            "output_sources"
                        ]
                    )
                ),
            }
        )

    return rows


def calculate_summary(
    claims: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """计算逐条陈述数据集摘要。"""

    method_summary: Dict[
        str,
        Dict[str, int],
    ] = {}

    for method_name in METHOD_ORDER:
        method_claims = [
            claim
            for claim in claims
            if claim["method"]
            == method_name
        ]

        primary_claims = [
            claim
            for claim in method_claims
            if not claim[
                "is_duplicate"
            ]
        ]

        core_claims = [
            claim
            for claim in primary_claims
            if claim[
                "included_in_core_consistency"
            ]
        ]

        auxiliary_claims = [
            claim
            for claim in primary_claims
            if not claim[
                "included_in_core_consistency"
            ]
        ]

        duplicate_claims = [
            claim
            for claim in method_claims
            if claim[
                "is_duplicate"
            ]
        ]

        method_summary[
            method_name
        ] = {
            "claim_count": len(
                method_claims
            ),
            "primary_claim_count": len(
                primary_claims
            ),
            "core_consistency_claim_count": (
                len(core_claims)
            ),
            "auxiliary_claim_count": (
                len(auxiliary_claims)
            ),
            "duplicate_claim_count": (
                len(duplicate_claims)
            ),
        }

    return {
        "claim_count": len(
            claims
        ),
        "primary_claim_count": sum(
            1
            for claim in claims
            if not claim[
                "is_duplicate"
            ]
        ),
        "core_consistency_claim_count": sum(
            1
            for claim in claims
            if (
                not claim[
                    "is_duplicate"
                ]
                and claim[
                    "included_in_core_consistency"
                ]
            )
        ),
        "auxiliary_claim_count": sum(
            1
            for claim in claims
            if (
                not claim[
                    "is_duplicate"
                ]
                and not claim[
                    "included_in_core_consistency"
                ]
            )
        ),
        "duplicate_claim_count": sum(
            1
            for claim in claims
            if claim[
                "is_duplicate"
            ]
        ),
        "method_summary": (
            method_summary
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "构建任务五证据一致性校验使用的"
            "逐条生成陈述数据集。"
        )
    )

    parser.add_argument(
        "--case-file",
        type=Path,
        default=DEFAULT_CASE_FILE,
    )

    parser.add_argument(
        "--result-dir",
        type=Path,
        default=DEFAULT_RESULT_DIRECTORY,
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

    args = parser.parse_args()

    case_file = resolve_path(
        args.case_file
    )

    result_directory = resolve_path(
        args.result_dir
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
        dataset = load_json(
            case_file
        )

        snapshot = load_json(
            evidence_snapshot_file
        )

        cases = dataset.get(
            "cases",
            [],
        )

        if not isinstance(cases, list):
            raise ValueError(
                "病例集中的 cases 必须是数组。"
            )

        if not cases:
            raise ValueError(
                "病例集不能为空。"
            )

        snapshot_mapping = (
            build_snapshot_mapping(
                snapshot
            )
        )

        all_claims: List[
            Dict[str, Any]
        ] = []

        structured_cases: List[
            Dict[str, Any]
        ] = []

        for case_index, case in enumerate(
            cases,
            start=1,
        ):
            if not isinstance(case, dict):
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

            user_observation = str(
                case.get(
                    "user_observation",
                    "",
                )
            ).strip()

            if case_id not in snapshot_mapping:
                raise ValueError(
                    f"证据快照缺少病例：{case_id}"
                )

            result_file = (
                result_directory
                / f"comparison_{case_id}.json"
            )

            experiment = load_json(
                result_file
            )

            snapshot_case = (
                snapshot_mapping[
                    case_id
                ]
            )

            method_entries: List[
                Dict[str, Any]
            ] = []

            print(
                f"[{case_index}/{len(cases)}] "
                f"正在拆分生成陈述：{case_id}"
            )

            for method_name in METHOD_ORDER:
                method_record = (
                    find_method_record(
                        experiment=experiment,
                        method_name=(
                            method_name
                        ),
                    )
                )

                result = method_record.get(
                    "result",
                    {},
                )

                if not isinstance(
                    result,
                    dict,
                ):
                    raise ValueError(
                        f"{case_id} 的 {method_name} "
                        "result 不是对象。"
                    )

                if (
                    result.get(
                        "run_status"
                    )
                    != "success"
                ):
                    raise ValueError(
                        f"{case_id} 的 {method_name} "
                        "不是成功结果。"
                    )

                evidence_scope = (
                    get_allowed_evidence(
                        method_name=(
                            method_name
                        ),
                        snapshot_case=(
                            snapshot_case
                        ),
                    )
                )

                claims = extract_claims(
                    case_id=case_id,
                    method_name=(
                        method_name
                    ),
                    result=result,
                    evidence_scope=(
                        evidence_scope
                    ),
                )

                if not claims:
                    raise ValueError(
                        f"{case_id} 的 {method_name} "
                        "没有可拆分陈述。"
                    )

                all_claims.extend(
                    claims
                )

                method_entries.append(
                    {
                        "method": (
                            method_name
                        ),
                        "model_name": str(
                            result.get(
                                "model_name",
                                "",
                            )
                        ),
                        "prompt_version": str(
                            result.get(
                                "prompt_version",
                                "",
                            )
                        ),
                        "allowed_evidence": (
                            evidence_scope
                        ),
                        "claim_count": len(
                            claims
                        ),
                        "claims": claims,
                    }
                )

            structured_cases.append(
                {
                    "case_id": case_id,
                    "candidate_disease": (
                        candidate_disease
                    ),
                    "user_observation": (
                        user_observation
                    ),
                    "expected_concepts": (
                        case.get(
                            "expected_concepts",
                            [],
                        )
                    ),
                    "methods": (
                        method_entries
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
            f"任务五逐条陈述数据集构建失败：{exc}"
        )
        return 1

    summary = calculate_summary(
        all_claims
    )

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_json = (
        output_directory
        / "task5_claim_dataset.json"
    )

    output_csv = (
        output_directory
        / "task5_claims.csv"
    )

    payload = {
        "dataset_name": (
            "task5_claim_level_dataset_v1"
        ),
        "dataset_version": "1.0",
        "generated_at": (
            current_time()
        ),
        "case_count": len(
            structured_cases
        ),
        "method_count": len(
            METHOD_ORDER
        ),
        "method_order": (
            METHOD_ORDER
        ),
        "input_hashes": {
            "case_file_sha256": (
                calculate_sha256(
                    case_file
                )
            ),
            "evidence_snapshot_sha256": (
                calculate_sha256(
                    evidence_snapshot_file
                )
            ),
        },
        "field_policy": (
            FIELD_POLICY
        ),
        "consistency_label_schema": {
            "supported": (
                "陈述能够被允许使用的证据直接支持。"
            ),
            "partially_supported": (
                "陈述只有部分内容得到证据支持，"
                "或表述范围超出证据。"
            ),
            "unsupported": (
                "允许使用的证据中没有支持该陈述的内容。"
            ),
            "contradicted": (
                "允许使用的证据与陈述存在明确冲突。"
            ),
            "unverifiable": (
                "当前没有外部证据，或证据不足以进行判断。"
            ),
            "not_applicable": (
                "该条目属于建议或证据缺口，"
                "不纳入核心事实一致性评价。"
            ),
        },
        "summary": summary,
        "cases": (
            structured_cases
        ),
    }

    write_json(
        payload=payload,
        file_path=output_json,
    )

    csv_rows = build_csv_rows(
        all_claims
    )

    write_csv(
        rows=csv_rows,
        file_path=output_csv,
    )

    print("=" * 70)
    print("任务五逐条陈述数据集构建完成")
    print("=" * 70)
    print(
        f"病例数量：{len(structured_cases)}"
    )
    print(
        f"方法结果数量："
        f"{len(structured_cases) * len(METHOD_ORDER)}"
    )
    print(
        f"生成陈述总数："
        f"{summary['claim_count']}"
    )
    print(
        "核心一致性陈述数："
        f"{summary['core_consistency_claim_count']}"
    )
    print(
        "辅助陈述数："
        f"{summary['auxiliary_claim_count']}"
    )
    print(
        "重复陈述数："
        f"{summary['duplicate_claim_count']}"
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
            f"总陈述="
            f"{method_summary['claim_count']} | "
            f"核心陈述="
            f"{method_summary['core_consistency_claim_count']} | "
            f"辅助陈述="
            f"{method_summary['auxiliary_claim_count']} | "
            f"重复陈述="
            f"{method_summary['duplicate_claim_count']}"
        )

    print("-" * 70)
    print(
        f"JSON 数据集：{output_json}"
    )
    print(
        f"CSV 数据集：{output_csv}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())