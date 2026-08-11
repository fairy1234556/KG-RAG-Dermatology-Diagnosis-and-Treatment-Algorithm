"""
构建任务四正式病例集使用的疾病证据蓝图 V2。

功能：
1. 读取 entity_nodes.csv 和 triples.csv；
2. 提取 7 类疾病的直接知识图谱证据；
3. 按皮损表现、部位、症状、检查、鉴别和风险等类别整理；
4. 建立跨疾病冲突特征池；
5. 记录知识图谱文件 SHA256；
6. 输出可供 140 条病例生成器使用的 JSON 蓝图。

本脚本不会调用大语言模型。

运行：
    python experiments/build_task4_disease_evidence_blueprint_v2.py
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


DEFAULT_ENTITY_FILE = (
    PROJECT_ROOT
    / "kg"
    / "csv"
    / "entity_nodes.csv"
)

DEFAULT_TRIPLE_FILE = (
    PROJECT_ROOT
    / "kg"
    / "csv"
    / "triples.csv"
)

DEFAULT_OUTPUT_FILE = (
    PROJECT_ROOT
    / "experiments"
    / "cases"
    / "task4_disease_evidence_blueprint_v2.json"
)


DISEASE_DEFINITIONS = [
    {
        "disease_id": "DIS_001",
        "disease_name_cn": "黑色素瘤",
        "disease_abbreviation": "MEL",
    },
    {
        "disease_id": "DIS_002",
        "disease_name_cn": "黑色素细胞痣",
        "disease_abbreviation": "NV",
    },
    {
        "disease_id": "DIS_003",
        "disease_name_cn": "基底细胞癌",
        "disease_abbreviation": "BCC",
    },
    {
        "disease_id": "DIS_004",
        "disease_name_cn": "光化性角化病/表皮内癌",
        "disease_abbreviation": "AKIEC",
    },
    {
        "disease_id": "DIS_005",
        "disease_name_cn": "良性角化样病变",
        "disease_abbreviation": "BKL",
    },
    {
        "disease_id": "DIS_006",
        "disease_name_cn": "皮肤纤维瘤",
        "disease_abbreviation": "DF",
    },
    {
        "disease_id": "DIS_007",
        "disease_name_cn": "血管性皮损",
        "disease_abbreviation": "VASC",
    },
]


EVIDENCE_CATEGORY_ORDER = [
    "lesion_features",
    "anatomical_sites",
    "symptoms",
    "examination_findings",
    "differential_diagnoses",
    "risk_warnings",
    "treatments",
    "causes_and_risk_factors",
    "other_evidence",
]


OBSERVATION_CATEGORIES = {
    "lesion_features",
    "anatomical_sites",
    "symptoms",
    "examination_findings",
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
    """将相对路径转换为项目目录下的绝对路径。"""

    if path.is_absolute():
        return path

    return PROJECT_ROOT / path


def read_csv_rows(
    file_path: Path,
) -> List[Dict[str, str]]:
    """读取 CSV 文件。"""

    if not file_path.exists():
        raise FileNotFoundError(
            f"找不到文件：{file_path}"
        )

    with file_path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        rows = list(
            csv.DictReader(file)
        )

    if not rows:
        raise ValueError(
            f"CSV 文件为空：{file_path}"
        )

    return rows


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


def unique_non_empty(
    values: Iterable[str],
) -> List[str]:
    """保留原顺序并去除空值和重复值。"""

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


def classify_evidence(
    relation_cn: str,
    tail_type: str,
) -> str:
    """根据关系和尾实体类型划分证据类别。"""

    relation = str(
        relation_cn or ""
    ).strip()

    entity_type = str(
        tail_type or ""
    ).strip()

    if entity_type == "LesionFeature":
        return "lesion_features"

    if entity_type == "AnatomicalSite":
        return "anatomical_sites"

    if entity_type == "Symptom":
        return "symptoms"

    if entity_type in {
        "Examination",
        "ExaminationFinding",
        "DermoscopyFeature",
        "PathologyFeature",
        "DiagnosticTest",
    }:
        return "examination_findings"

    if entity_type in {
        "DifferentialDiagnosis",
        "DifferentialDisease",
    }:
        return "differential_diagnoses"

    if entity_type == "RiskWarning":
        return "risk_warnings"

    if entity_type in {
        "Treatment",
        "TreatmentMethod",
    }:
        return "treatments"

    if entity_type in {
        "Cause",
        "RiskFactor",
        "Etiology",
    }:
        return "causes_and_risk_factors"

    if (
        "表现" in relation
        or "特征" in relation
    ):
        return "lesion_features"

    if (
        "常见于" in relation
        or "好发于" in relation
        or "部位" in relation
    ):
        return "anatomical_sites"

    if "症状" in relation:
        return "symptoms"

    if (
        "检查" in relation
        or "皮肤镜" in relation
        or "病理" in relation
    ):
        return "examination_findings"

    if "鉴别" in relation:
        return "differential_diagnoses"

    if (
        "风险" in relation
        or "警示" in relation
        or "提示" in relation
    ):
        return "risk_warnings"

    if (
        "治疗" in relation
        or "处理" in relation
    ):
        return "treatments"

    if (
        "病因" in relation
        or "危险因素" in relation
        or "相关因素" in relation
    ):
        return "causes_and_risk_factors"

    return "other_evidence"


def serialize_triple(
    triple: Dict[str, str],
) -> Dict[str, Any]:
    """将三元组转换为蓝图证据记录。"""

    relation_cn = str(
        triple.get(
            "relation_cn",
            "",
        )
    ).strip()

    tail_type = str(
        triple.get(
            "tail_type",
            "",
        )
    ).strip()

    category = classify_evidence(
        relation_cn=relation_cn,
        tail_type=tail_type,
    )

    return {
        "triple_id": str(
            triple.get(
                "triple_id",
                "",
            )
        ).strip(),
        "head_id": str(
            triple.get(
                "head_id",
                "",
            )
        ).strip(),
        "head_cn": str(
            triple.get(
                "head_cn",
                "",
            )
        ).strip(),
        "head_type": str(
            triple.get(
                "head_type",
                "",
            )
        ).strip(),
        "relation_cn": relation_cn,
        "relation_en": str(
            triple.get(
                "relation_en",
                "",
            )
        ).strip(),
        "tail_id": str(
            triple.get(
                "tail_id",
                "",
            )
        ).strip(),
        "tail_cn": str(
            triple.get(
                "tail_cn",
                "",
            )
        ).strip(),
        "tail_type": tail_type,
        "source": str(
            triple.get(
                "source",
                "",
            )
        ).strip(),
        "evidence_text": str(
            triple.get(
                "evidence_text",
                "",
            )
        ).strip(),
        "note": str(
            triple.get(
                "note",
                "",
            )
        ).strip(),
        "evidence_category": category,
    }


def validate_required_columns(
    rows: List[Dict[str, str]],
    required_columns: List[str],
    file_name: str,
) -> None:
    """验证 CSV 必需字段。"""

    available_columns = set(
        rows[0].keys()
    )

    missing_columns = [
        column
        for column in required_columns
        if column not in available_columns
    ]

    if missing_columns:
        raise ValueError(
            f"{file_name} 缺少字段："
            f"{missing_columns}"
        )


def validate_unique_values(
    values: List[str],
    value_name: str,
) -> None:
    """验证字段值唯一。"""

    counter = Counter(values)

    duplicates = sorted(
        value
        for value, count in counter.items()
        if value and count > 1
    )

    if duplicates:
        raise ValueError(
            f"{value_name} 存在重复值："
            f"{duplicates}"
        )


def build_entity_mapping(
    entity_rows: List[Dict[str, str]],
) -> Dict[str, Dict[str, str]]:
    """按实体编号建立索引。"""

    mapping: Dict[
        str,
        Dict[str, str],
    ] = {}

    for row in entity_rows:
        entity_id = str(
            row.get(
                "id",
                "",
            )
        ).strip()

        if entity_id:
            mapping[entity_id] = row

    return mapping


def build_disease_evidence_records(
    disease_id: str,
    disease_name: str,
    triple_rows: List[Dict[str, str]],
) -> List[Dict[str, Any]]:
    """提取某疾病作为头实体的直接证据。"""

    matched_records = [
        serialize_triple(row)
        for row in triple_rows
        if (
            str(
                row.get(
                    "head_id",
                    "",
                )
            ).strip()
            == disease_id
            or str(
                row.get(
                    "head_cn",
                    "",
                )
            ).strip()
            == disease_name
        )
    ]

    matched_records.sort(
        key=lambda record: (
            record["triple_id"]
        )
    )

    return matched_records


def build_category_mapping(
    evidence_records: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """按证据类别分组。"""

    category_mapping: Dict[
        str,
        List[Dict[str, Any]],
    ] = {
        category: []
        for category in EVIDENCE_CATEGORY_ORDER
    }

    for record in evidence_records:
        category = record[
            "evidence_category"
        ]

        if category not in category_mapping:
            category_mapping[
                "other_evidence"
            ].append(
                record
            )
        else:
            category_mapping[
                category
            ].append(
                record
            )

    return category_mapping


def build_distribution(
    values: Iterable[str],
) -> Dict[str, int]:
    """计算值分布并按名称排序。"""

    counter = Counter(
        value
        for value in values
        if value
    )

    return {
        key: counter[key]
        for key in sorted(
            counter.keys()
        )
    }


def build_disease_entry(
    disease_definition: Dict[str, str],
    entity_mapping: Dict[str, Dict[str, str]],
    triple_rows: List[Dict[str, str]],
) -> Dict[str, Any]:
    """构建单个疾病的证据蓝图。"""

    disease_id = disease_definition[
        "disease_id"
    ]

    expected_name = disease_definition[
        "disease_name_cn"
    ]

    if disease_id not in entity_mapping:
        raise ValueError(
            f"实体文件缺少疾病：{disease_id}"
        )

    disease_entity = entity_mapping[
        disease_id
    ]

    actual_name = str(
        disease_entity.get(
            "name_cn",
            "",
        )
    ).strip()

    if actual_name != expected_name:
        raise ValueError(
            f"{disease_id} 名称不一致："
            f"预期={expected_name}，"
            f"实际={actual_name}"
        )

    if (
        str(
            disease_entity.get(
                "entity_type",
                "",
            )
        ).strip()
        != "Disease"
    ):
        raise ValueError(
            f"{disease_id} 不是 Disease 实体。"
        )

    evidence_records = (
        build_disease_evidence_records(
            disease_id=disease_id,
            disease_name=expected_name,
            triple_rows=triple_rows,
        )
    )

    if not evidence_records:
        raise ValueError(
            f"{expected_name} 没有直接知识图谱证据。"
        )

    incomplete_records = [
        record["triple_id"]
        for record in evidence_records
        if (
            not record["triple_id"]
            or not record["tail_cn"]
            or not record["source"]
            or not record["evidence_text"]
        )
    ]

    if incomplete_records:
        raise ValueError(
            f"{expected_name} 存在不完整证据记录："
            f"{incomplete_records}"
        )

    category_mapping = (
        build_category_mapping(
            evidence_records
        )
    )

    observation_support_record_ids = [
        record["triple_id"]
        for category in OBSERVATION_CATEGORIES
        for record in category_mapping[
            category
        ]
    ]

    auxiliary_record_ids = [
        record["triple_id"]
        for category in EVIDENCE_CATEGORY_ORDER
        if category not in OBSERVATION_CATEGORIES
        for record in category_mapping[
            category
        ]
    ]

    source_names = unique_non_empty(
        record["source"]
        for record in evidence_records
    )

    return {
        "disease_id": disease_id,
        "disease_name_cn": expected_name,
        "disease_name_en": str(
            disease_entity.get(
                "name_en",
                "",
            )
        ).strip(),
        "alias": str(
            disease_entity.get(
                "alias",
                "",
            )
        ).strip(),
        "disease_abbreviation": (
            disease_definition[
                "disease_abbreviation"
            ]
        ),
        "entity_source": str(
            disease_entity.get(
                "source",
                "",
            )
        ).strip(),
        "outgoing_evidence_count": len(
            evidence_records
        ),
        "observation_support_count": len(
            observation_support_record_ids
        ),
        "auxiliary_evidence_count": len(
            auxiliary_record_ids
        ),
        "relation_distribution": (
            build_distribution(
                record["relation_cn"]
                for record in evidence_records
            )
        ),
        "tail_type_distribution": (
            build_distribution(
                record["tail_type"]
                for record in evidence_records
            )
        ),
        "source_names": source_names,
        "observation_support_record_ids": (
            observation_support_record_ids
        ),
        "auxiliary_record_ids": (
            auxiliary_record_ids
        ),
        "evidence_by_category": (
            category_mapping
        ),
    }


def add_cross_disease_conflict_pools(
    disease_entries: List[Dict[str, Any]],
) -> None:
    """为每种疾病增加其他疾病的观察特征引用池。"""

    for disease in disease_entries:
        conflict_sources: List[
            Dict[str, Any]
        ] = []

        for other_disease in disease_entries:
            if (
                other_disease["disease_id"]
                == disease["disease_id"]
            ):
                continue

            conflict_sources.append(
                {
                    "source_disease_id": (
                        other_disease[
                            "disease_id"
                        ]
                    ),
                    "source_disease_name_cn": (
                        other_disease[
                            "disease_name_cn"
                        ]
                    ),
                    "source_disease_abbreviation": (
                        other_disease[
                            "disease_abbreviation"
                        ]
                    ),
                    "observation_support_record_ids": (
                        other_disease[
                            "observation_support_record_ids"
                        ]
                    ),
                }
            )

        disease[
            "cross_disease_conflict_sources"
        ] = conflict_sources


def write_json_atomic(
    payload: Dict[str, Any],
    output_file: Path,
) -> None:
    """原子方式写入 JSON。"""

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_file = (
        output_file.with_suffix(
            output_file.suffix + ".tmp"
        )
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
        output_file
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "根据当前知识图谱构建任务四"
            "正式病例疾病证据蓝图。"
        )
    )

    parser.add_argument(
        "--entity-file",
        type=Path,
        default=DEFAULT_ENTITY_FILE,
    )

    parser.add_argument(
        "--triple-file",
        type=Path,
        default=DEFAULT_TRIPLE_FILE,
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_FILE,
    )

    args = parser.parse_args()

    entity_file = resolve_path(
        args.entity_file
    )

    triple_file = resolve_path(
        args.triple_file
    )

    output_file = resolve_path(
        args.output
    )

    try:
        entity_rows = read_csv_rows(
            entity_file
        )

        triple_rows = read_csv_rows(
            triple_file
        )

        validate_required_columns(
            rows=entity_rows,
            required_columns=[
                "id",
                "entity_type",
                "name_cn",
                "name_en",
                "alias",
                "source",
                "note",
            ],
            file_name="entity_nodes.csv",
        )

        validate_required_columns(
            rows=triple_rows,
            required_columns=[
                "triple_id",
                "head_id",
                "head_cn",
                "head_type",
                "relation_cn",
                "relation_en",
                "tail_id",
                "tail_cn",
                "tail_type",
                "source",
                "evidence_text",
                "note",
            ],
            file_name="triples.csv",
        )

        validate_unique_values(
            values=[
                str(
                    row.get(
                        "id",
                        "",
                    )
                ).strip()
                for row in entity_rows
            ],
            value_name="实体编号",
        )

        validate_unique_values(
            values=[
                str(
                    row.get(
                        "triple_id",
                        "",
                    )
                ).strip()
                for row in triple_rows
            ],
            value_name="三元组编号",
        )

        entity_mapping = (
            build_entity_mapping(
                entity_rows
            )
        )

        disease_entries = [
            build_disease_entry(
                disease_definition=(
                    disease_definition
                ),
                entity_mapping=(
                    entity_mapping
                ),
                triple_rows=(
                    triple_rows
                ),
            )
            for disease_definition
            in DISEASE_DEFINITIONS
        ]

        add_cross_disease_conflict_pools(
            disease_entries
        )

    except (
        FileNotFoundError,
        ValueError,
        csv.Error,
    ) as exc:
        print(
            f"疾病证据蓝图构建失败：{exc}"
        )
        return 1

    total_disease_evidence_count = sum(
        disease[
            "outgoing_evidence_count"
        ]
        for disease in disease_entries
    )

    total_observation_support_count = sum(
        disease[
            "observation_support_count"
        ]
        for disease in disease_entries
    )

    payload = {
        "blueprint_name": (
            "task4_disease_evidence_blueprint_v2"
        ),
        "blueprint_version": "2.0",
        "generated_at": current_time(),
        "description": (
            "基于当前知识图谱自动提取的"
            "7 类皮肤疾病正式病例生成证据蓝图。"
        ),
        "disease_count": len(
            disease_entries
        ),
        "source_entity_count": len(
            entity_rows
        ),
        "source_triple_count": len(
            triple_rows
        ),
        "total_disease_evidence_count": (
            total_disease_evidence_count
        ),
        "total_observation_support_count": (
            total_observation_support_count
        ),
        "source_files": {
            "entity_nodes": {
                "path": str(
                    entity_file.relative_to(
                        PROJECT_ROOT
                    )
                ),
                "sha256": calculate_sha256(
                    entity_file
                ),
            },
            "triples": {
                "path": str(
                    triple_file.relative_to(
                        PROJECT_ROOT
                    )
                ),
                "sha256": calculate_sha256(
                    triple_file
                ),
            },
        },
        "evidence_category_order": (
            EVIDENCE_CATEGORY_ORDER
        ),
        "observation_categories": sorted(
            OBSERVATION_CATEGORIES
        ),
        "diseases": disease_entries,
    }

    write_json_atomic(
        payload=payload,
        output_file=output_file,
    )

    print("=" * 72)
    print("任务四疾病证据蓝图构建完成")
    print("=" * 72)
    print(
        f"疾病数量：{len(disease_entries)}"
    )
    print(
        "疾病直接证据总数："
        f"{total_disease_evidence_count}"
    )
    print(
        "可用于观察病例构造的证据总数："
        f"{total_observation_support_count}"
    )
    print("-" * 72)

    for disease in disease_entries:
        category_counts = {
            category: len(
                disease[
                    "evidence_by_category"
                ][category]
            )
            for category
            in EVIDENCE_CATEGORY_ORDER
            if disease[
                "evidence_by_category"
            ][category]
        }

        print(
            f"{disease['disease_id']} | "
            f"{disease['disease_name_cn']} | "
            f"全部证据="
            f"{disease['outgoing_evidence_count']} | "
            f"观察证据="
            f"{disease['observation_support_count']} | "
            f"类别={category_counts}"
        )

    print("-" * 72)
    print(
        f"输出文件：{output_file}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())