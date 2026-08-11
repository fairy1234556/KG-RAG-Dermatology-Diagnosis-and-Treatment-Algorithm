"""
生成任务四正式测试病例集 V2。

目标：
- 7 类疾病；
- 每类 20 条；
- 每类包含 5 种病例类型；
- 每种类型 4 条；
- 总计 140 条。

病例全部根据：
experiments/cases/task4_disease_evidence_blueprint_v2.json

确定性构造。

本脚本不会调用大语言模型。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


DEFAULT_BLUEPRINT_FILE = (
    PROJECT_ROOT
    / "experiments"
    / "cases"
    / "task4_disease_evidence_blueprint_v2.json"
)

DEFAULT_OUTPUT_FILE = (
    PROJECT_ROOT
    / "experiments"
    / "cases"
    / "task4_cases_v2.json"
)


CASE_TYPES = [
    "typical_positive",
    "partial_support",
    "evidence_insufficient",
    "differential_confusion",
    "conflict_difficult",
]


CASE_TYPE_ABBREVIATIONS = {
    "typical_positive": "TP",
    "partial_support": "PS",
    "evidence_insufficient": "EI",
    "differential_confusion": "DC",
    "conflict_difficult": "CD",
}


FEATURE_COMBINATIONS_3 = [
    (0, 1, 2),
    (1, 2, 3),
    (0, 2, 3),
    (0, 1, 3),
]


FEATURE_COMBINATIONS_2 = [
    (0, 1),
    (1, 2),
    (2, 3),
    (0, 3),
]


GENERIC_INSUFFICIENT_FEATURES = [
    "局部皮肤颜色改变",
    "局部小丘疹",
    "局部斑片样皮损",
    "局部形态不明确的皮损",
]


CONFUSION_MAP = {
    "黑色素瘤": [
        "黑色素细胞痣",
        "良性角化样病变",
    ],
    "黑色素细胞痣": [
        "黑色素瘤",
        "皮肤纤维瘤",
    ],
    "基底细胞癌": [
        "良性角化样病变",
        "光化性角化病/表皮内癌",
    ],
    "光化性角化病/表皮内癌": [
        "基底细胞癌",
        "良性角化样病变",
    ],
    "良性角化样病变": [
        "黑色素瘤",
        "基底细胞癌",
    ],
    "皮肤纤维瘤": [
        "黑色素细胞痣",
        "良性角化样病变",
    ],
    "血管性皮损": [
        "皮肤纤维瘤",
        "基底细胞癌",
    ],
}


MISSING_INFORMATION = {
    "typical_positive": [
        "皮肤镜检查结果",
        "组织病理检查结果",
    ],
    "partial_support": [
        "更多皮损形态特征",
        "皮肤镜检查结果",
        "组织病理检查结果",
    ],
    "evidence_insufficient": [
        "更多皮损形态特征",
        "明确病程信息",
        "皮肤镜检查结果",
        "组织病理检查结果",
    ],
    "differential_confusion": [
        "皮肤镜检查结果",
        "组织病理检查结果",
        "病程变化信息",
    ],
    "conflict_difficult": [
        "皮肤镜检查结果",
        "组织病理检查结果",
        "能够解释冲突表现的进一步检查信息",
    ],
}


def current_time() -> str:
    """返回当前时间。"""

    return (
        datetime.now()
        .astimezone()
        .isoformat(
            timespec="seconds"
        )
    )


def load_json(
    file_path: Path,
) -> Dict[str, Any]:
    """读取 JSON 文件。"""

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
            "JSON 根节点必须是对象。"
        )

    return payload


def calculate_sha256(
    file_path: Path,
) -> str:
    """计算 SHA256。"""

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
    """保留顺序，删除空值和重复值。"""

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


def cycle_get(
    records: Sequence[Dict[str, Any]],
    index: int,
) -> Dict[str, Any]:
    """循环取得证据记录。"""

    if not records:
        raise ValueError(
            "证据记录为空，无法生成病例。"
        )

    return records[
        index % len(records)
    ]


def select_records(
    records: Sequence[Dict[str, Any]],
    indexes: Sequence[int],
) -> List[Dict[str, Any]]:
    """根据索引选择证据。"""

    if not records:
        raise ValueError(
            "可选证据为空。"
        )

    selected: List[
        Dict[str, Any]
    ] = []

    for index in indexes:
        record = cycle_get(
            records,
            index,
        )

        if (
            record["triple_id"]
            not in {
                item["triple_id"]
                for item in selected
            }
        ):
            selected.append(
                record
            )

    return selected


def get_category(
    disease: Dict[str, Any],
    category: str,
) -> List[Dict[str, Any]]:
    """取得疾病的某一类证据。"""

    evidence_mapping = disease.get(
        "evidence_by_category",
        {},
    )

    if not isinstance(
        evidence_mapping,
        dict,
    ):
        return []

    records = evidence_mapping.get(
        category,
        [],
    )

    if not isinstance(records, list):
        return []

    return [
        record
        for record in records
        if isinstance(
            record,
            dict,
        )
    ]


def get_concepts(
    records: Sequence[Dict[str, Any]],
) -> List[str]:
    """取得证据尾实体名称。"""

    return unique_non_empty(
        str(
            record.get(
                "tail_cn",
                "",
            )
        )
        for record in records
    )


def get_source_ids(
    records: Sequence[Dict[str, Any]],
) -> List[str]:
    """取得三元组编号。"""

    return unique_non_empty(
        str(
            record.get(
                "triple_id",
                "",
            )
        )
        for record in records
    )


def build_observation_text(
    lesion_features: Sequence[str],
    anatomical_site: str = "",
    symptoms: Sequence[str] = (),
    prefix_index: int = 0,
) -> str:
    """构造自然语言观察文本。"""

    prefixes = [
        "患者发现",
        "观察到患者",
        "患者近期注意到",
        "患者自述发现",
    ]

    prefix = prefixes[
        prefix_index
        % len(prefixes)
    ]

    feature_text = "、".join(
        unique_non_empty(
            lesion_features
        )
    )

    if anatomical_site:
        sentence = (
            f"{prefix}{anatomical_site}"
            f"存在皮损，主要表现为"
            f"{feature_text}。"
        )
    else:
        sentence = (
            f"{prefix}局部皮肤存在皮损，"
            f"主要表现为{feature_text}。"
        )

    symptom_values = unique_non_empty(
        symptoms
    )

    if symptom_values:
        symptom_text = "、".join(
            symptom_values
        )

        sentence += (
            f"同时可见或自述{symptom_text}。"
        )

    return sentence


def make_case_id(
    disease_abbreviation: str,
    case_type: str,
    index: int,
) -> str:
    """生成病例编号。"""

    type_abbreviation = (
        CASE_TYPE_ABBREVIATIONS[
            case_type
        ]
    )

    return (
        f"CASE_{disease_abbreviation}_"
        f"{type_abbreviation}_"
        f"{index + 1:03d}"
    )


def make_base_case(
    disease: Dict[str, Any],
    case_type: str,
    index: int,
) -> Dict[str, Any]:
    """生成病例公共字段。"""

    disease_name = str(
        disease[
            "disease_name_cn"
        ]
    )

    return {
        "case_id": make_case_id(
            disease_abbreviation=str(
                disease[
                    "disease_abbreviation"
                ]
            ),
            case_type=case_type,
            index=index,
        ),
        "true_label": disease_name,
        "candidate_disease": (
            disease_name
        ),
        "observation_text": "",
        "lesion_features": [],
        "anatomical_site": "",
        "symptoms": [],
        "duration_change": "",
        "difficulty_level": "",
        "case_type": case_type,
        "expected_concepts": [],
        "supporting_concepts": [],
        "conflicting_concepts": [],
        "missing_information": list(
            MISSING_INFORMATION[
                case_type
            ]
        ),
        "evidence_expectation": "",
        "data_origin": (
            "synthetic_kg_grounded"
        ),
        "source_basis": [],
        "generation_rule": (
            "task4_case_generation_v2"
        ),
    }


def build_typical_positive_case(
    disease: Dict[str, Any],
    index: int,
) -> Dict[str, Any]:
    """生成典型支持型病例。"""

    case = make_base_case(
        disease=disease,
        case_type="typical_positive",
        index=index,
    )

    lesion_records = get_category(
        disease,
        "lesion_features",
    )

    site_records = get_category(
        disease,
        "anatomical_sites",
    )

    symptom_records = get_category(
        disease,
        "symptoms",
    )

    if len(lesion_records) < 4:
        raise ValueError(
            f"{disease['disease_name_cn']} "
            "皮损特征少于 4 条。"
        )

    feature_records = select_records(
        lesion_records,
        FEATURE_COMBINATIONS_3[
            index
        ],
    )

    site_record = (
        cycle_get(
            site_records,
            index,
        )
        if site_records
        else None
    )

    symptom_record = (
        cycle_get(
            symptom_records,
            index,
        )
        if symptom_records
        else None
    )

    feature_concepts = (
        get_concepts(
            feature_records
        )
    )

    site = (
        str(
            site_record[
                "tail_cn"
            ]
        )
        if site_record
        else ""
    )

    symptoms = (
        [
            str(
                symptom_record[
                    "tail_cn"
                ]
            )
        ]
        if symptom_record
        else []
    )

    selected_records = list(
        feature_records
    )

    if site_record:
        selected_records.append(
            site_record
        )

    if symptom_record:
        selected_records.append(
            symptom_record
        )

    expected_concepts = (
        feature_concepts
        + ([site] if site else [])
        + symptoms
    )

    case[
        "observation_text"
    ] = build_observation_text(
        lesion_features=(
            feature_concepts
        ),
        anatomical_site=site,
        symptoms=symptoms,
        prefix_index=index,
    )

    case[
        "lesion_features"
    ] = feature_concepts

    case[
        "anatomical_site"
    ] = site

    case[
        "symptoms"
    ] = symptoms

    case[
        "difficulty_level"
    ] = (
        "easy"
        if index < 2
        else "medium"
    )

    case[
        "expected_concepts"
    ] = unique_non_empty(
        expected_concepts
    )

    case[
        "supporting_concepts"
    ] = unique_non_empty(
        expected_concepts
    )

    case[
        "conflicting_concepts"
    ] = []

    case[
        "evidence_expectation"
    ] = "sufficient"

    case[
        "source_basis"
    ] = get_source_ids(
        selected_records
    )

    return case


def build_partial_support_case(
    disease: Dict[str, Any],
    index: int,
) -> Dict[str, Any]:
    """生成部分支持型病例。"""

    case = make_base_case(
        disease=disease,
        case_type="partial_support",
        index=index,
    )

    lesion_records = get_category(
        disease,
        "lesion_features",
    )

    site_records = get_category(
        disease,
        "anatomical_sites",
    )

    feature_record = cycle_get(
        lesion_records,
        index,
    )

    feature = str(
        feature_record[
            "tail_cn"
        ]
    )

    selected_records = [
        feature_record
    ]

    site = ""

    if (
        site_records
        and index % 2 == 1
    ):
        site_record = cycle_get(
            site_records,
            index,
        )

        site = str(
            site_record[
                "tail_cn"
            ]
        )

        selected_records.append(
            site_record
        )

    concepts = [
        feature
    ]

    if site:
        concepts.append(
            site
        )

    case[
        "observation_text"
    ] = build_observation_text(
        lesion_features=[
            feature
        ],
        anatomical_site=site,
        prefix_index=index,
    )

    case[
        "lesion_features"
    ] = [
        feature
    ]

    case[
        "anatomical_site"
    ] = site

    case[
        "difficulty_level"
    ] = "medium"

    case[
        "expected_concepts"
    ] = unique_non_empty(
        concepts
    )

    case[
        "supporting_concepts"
    ] = unique_non_empty(
        concepts
    )

    case[
        "conflicting_concepts"
    ] = []

    case[
        "evidence_expectation"
    ] = "partial"

    case[
        "source_basis"
    ] = get_source_ids(
        selected_records
    )

    return case


def build_evidence_insufficient_case(
    disease: Dict[str, Any],
    index: int,
) -> Dict[str, Any]:
    """生成证据不足型病例。"""

    case = make_base_case(
        disease=disease,
        case_type="evidence_insufficient",
        index=index,
    )

    site_records = get_category(
        disease,
        "anatomical_sites",
    )

    symptom_records = get_category(
        disease,
        "symptoms",
    )

    weak_records = (
        site_records
        + symptom_records
    )

    if not weak_records:
        weak_records = get_category(
            disease,
            "lesion_features",
        )

    weak_record = cycle_get(
        weak_records,
        index,
    )

    weak_concept = str(
        weak_record[
            "tail_cn"
        ]
    )

    generic_feature = (
        GENERIC_INSUFFICIENT_FEATURES[
            index
        ]
    )

    anatomical_site = ""

    symptoms: List[str] = []

    if (
        weak_record.get(
            "tail_type"
        )
        == "AnatomicalSite"
    ):
        anatomical_site = (
            weak_concept
        )

    elif (
        weak_record.get(
            "tail_type"
        )
        == "Symptom"
    ):
        symptoms = [
            weak_concept
        ]

    case[
        "observation_text"
    ] = build_observation_text(
        lesion_features=[
            generic_feature
        ],
        anatomical_site=(
            anatomical_site
        ),
        symptoms=symptoms,
        prefix_index=index,
    )

    case[
        "lesion_features"
    ] = [
        generic_feature
    ]

    case[
        "anatomical_site"
    ] = anatomical_site

    case[
        "symptoms"
    ] = symptoms

    case[
        "difficulty_level"
    ] = "medium"

    case[
        "expected_concepts"
    ] = [
        weak_concept
    ]

    case[
        "supporting_concepts"
    ] = [
        weak_concept
    ]

    case[
        "conflicting_concepts"
    ] = []

    case[
        "evidence_expectation"
    ] = "insufficient"

    case[
        "source_basis"
    ] = [
        str(
            weak_record[
                "triple_id"
            ]
        )
    ]

    return case


def get_confusion_disease(
    disease_name: str,
    index: int,
    disease_mapping: Dict[
        str,
        Dict[str, Any]
    ],
) -> Dict[str, Any]:
    """取得对应的混淆疾病。"""

    candidates = CONFUSION_MAP.get(
        disease_name,
        [],
    )

    if not candidates:
        raise ValueError(
            f"缺少混淆疾病配置："
            f"{disease_name}"
        )

    confusion_name = candidates[
        index % len(candidates)
    ]

    if confusion_name not in disease_mapping:
        raise ValueError(
            f"疾病蓝图中不存在混淆疾病："
            f"{confusion_name}"
        )

    return disease_mapping[
        confusion_name
    ]


def build_differential_confusion_case(
    disease: Dict[str, Any],
    index: int,
    disease_mapping: Dict[
        str,
        Dict[str, Any]
    ],
) -> Dict[str, Any]:
    """生成鉴别混淆型病例。"""

    case = make_base_case(
        disease=disease,
        case_type="differential_confusion",
        index=index,
    )

    candidate_name = str(
        disease[
            "disease_name_cn"
        ]
    )

    true_disease = (
        get_confusion_disease(
            disease_name=(
                candidate_name
            ),
            index=index,
            disease_mapping=(
                disease_mapping
            ),
        )
    )

    candidate_features = (
        get_category(
            disease,
            "lesion_features",
        )
    )

    true_features = (
        get_category(
            true_disease,
            "lesion_features",
        )
    )

    true_sites = get_category(
        true_disease,
        "anatomical_sites",
    )

    candidate_record = (
        cycle_get(
            candidate_features,
            index,
        )
    )

    conflict_records = (
        select_records(
            true_features,
            FEATURE_COMBINATIONS_2[
                index
            ],
        )
    )

    site_record = (
        cycle_get(
            true_sites,
            index,
        )
        if true_sites
        else None
    )

    candidate_concept = str(
        candidate_record[
            "tail_cn"
        ]
    )

    conflict_concepts = (
        get_concepts(
            conflict_records
        )
    )

    site = (
        str(
            site_record[
                "tail_cn"
            ]
        )
        if site_record
        else ""
    )

    lesion_features = (
        [candidate_concept]
        + conflict_concepts
    )

    selected_records = (
        [candidate_record]
        + conflict_records
    )

    if site_record:
        selected_records.append(
            site_record
        )

    case[
        "true_label"
    ] = str(
        true_disease[
            "disease_name_cn"
        ]
    )

    case[
        "candidate_disease"
    ] = candidate_name

    case[
        "observation_text"
    ] = build_observation_text(
        lesion_features=(
            lesion_features
        ),
        anatomical_site=site,
        prefix_index=index,
    )

    case[
        "lesion_features"
    ] = unique_non_empty(
        lesion_features
    )

    case[
        "anatomical_site"
    ] = site

    case[
        "difficulty_level"
    ] = "hard"

    case[
        "expected_concepts"
    ] = unique_non_empty(
        lesion_features
        + ([site] if site else [])
    )

    case[
        "supporting_concepts"
    ] = [
        candidate_concept
    ]

    case[
        "conflicting_concepts"
    ] = unique_non_empty(
        conflict_concepts
        + ([site] if site else [])
    )

    case[
        "evidence_expectation"
    ] = "conflicting"

    case[
        "source_basis"
    ] = get_source_ids(
        selected_records
    )

    return case


def build_conflict_difficult_case(
    disease: Dict[str, Any],
    index: int,
    disease_mapping: Dict[
        str,
        Dict[str, Any]
    ],
) -> Dict[str, Any]:
    """生成冲突困难型病例。"""

    case = make_base_case(
        disease=disease,
        case_type="conflict_difficult",
        index=index,
    )

    disease_name = str(
        disease[
            "disease_name_cn"
        ]
    )

    conflict_disease = (
        get_confusion_disease(
            disease_name=(
                disease_name
            ),
            index=index + 1,
            disease_mapping=(
                disease_mapping
            ),
        )
    )

    support_features = (
        get_category(
            disease,
            "lesion_features",
        )
    )

    conflict_features = (
        get_category(
            conflict_disease,
            "lesion_features",
        )
    )

    site_records = get_category(
        disease,
        "anatomical_sites",
    )

    support_records = (
        select_records(
            support_features,
            FEATURE_COMBINATIONS_2[
                index
            ],
        )
    )

    conflict_records = (
        select_records(
            conflict_features,
            FEATURE_COMBINATIONS_2[
                (index + 1)
                % len(
                    FEATURE_COMBINATIONS_2
                )
            ],
        )
    )

    site_record = (
        cycle_get(
            site_records,
            index,
        )
        if site_records
        else None
    )

    support_concepts = (
        get_concepts(
            support_records
        )
    )

    conflict_concepts = (
        get_concepts(
            conflict_records
        )
    )

    site = (
        str(
            site_record[
                "tail_cn"
            ]
        )
        if site_record
        else ""
    )

    all_features = (
        support_concepts
        + conflict_concepts
    )

    selected_records = (
        support_records
        + conflict_records
    )

    if site_record:
        selected_records.append(
            site_record
        )

    case[
        "observation_text"
    ] = build_observation_text(
        lesion_features=(
            all_features
        ),
        anatomical_site=site,
        prefix_index=index,
    )

    case[
        "lesion_features"
    ] = unique_non_empty(
        all_features
    )

    case[
        "anatomical_site"
    ] = site

    case[
        "difficulty_level"
    ] = "hard"

    case[
        "expected_concepts"
    ] = unique_non_empty(
        all_features
        + ([site] if site else [])
    )

    case[
        "supporting_concepts"
    ] = unique_non_empty(
        support_concepts
        + ([site] if site else [])
    )

    case[
        "conflicting_concepts"
    ] = unique_non_empty(
        conflict_concepts
    )

    case[
        "evidence_expectation"
    ] = "conflicting"

    case[
        "source_basis"
    ] = get_source_ids(
        selected_records
    )

    return case


def generate_cases(
    diseases: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """生成全部 140 条病例。"""

    disease_mapping = {
        str(
            disease[
                "disease_name_cn"
            ]
        ): disease
        for disease in diseases
    }

    cases: List[
        Dict[str, Any]
    ] = []

    for disease in diseases:
        disease_name = str(
            disease[
                "disease_name_cn"
            ]
        )

        print(
            f"正在生成：{disease_name}"
        )

        for index in range(4):
            cases.append(
                build_typical_positive_case(
                    disease,
                    index,
                )
            )

        for index in range(4):
            cases.append(
                build_partial_support_case(
                    disease,
                    index,
                )
            )

        for index in range(4):
            cases.append(
                build_evidence_insufficient_case(
                    disease,
                    index,
                )
            )

        for index in range(4):
            cases.append(
                build_differential_confusion_case(
                    disease=disease,
                    index=index,
                    disease_mapping=(
                        disease_mapping
                    ),
                )
            )

        for index in range(4):
            cases.append(
                build_conflict_difficult_case(
                    disease=disease,
                    index=index,
                    disease_mapping=(
                        disease_mapping
                    ),
                )
            )

    return cases


def validate_generation(
    cases: List[Dict[str, Any]],
) -> None:
    """执行基础生成结果检查。"""

    if len(cases) != 140:
        raise ValueError(
            f"病例总数应为 140，"
            f"实际为 {len(cases)}。"
        )

    case_ids = [
        str(
            case["case_id"]
        )
        for case in cases
    ]

    if len(
        set(case_ids)
    ) != len(
        case_ids
    ):
        raise ValueError(
            "case_id 存在重复。"
        )

    candidate_distribution = Counter(
        case[
            "candidate_disease"
        ]
        for case in cases
    )

    for disease_name, count in (
        candidate_distribution.items()
    ):
        if count != 20:
            raise ValueError(
                f"{disease_name} "
                f"候选病例数应为 20，"
                f"实际为 {count}。"
            )

    type_distribution = Counter(
        case[
            "case_type"
        ]
        for case in cases
    )

    for case_type in CASE_TYPES:
        count = type_distribution[
            case_type
        ]

        if count != 28:
            raise ValueError(
                f"{case_type} "
                f"应为 28 条，"
                f"实际为 {count}。"
            )

    for case in cases:
        if not case[
            "observation_text"
        ]:
            raise ValueError(
                f"{case['case_id']} "
                "observation_text 为空。"
            )

        if not case[
            "lesion_features"
        ]:
            raise ValueError(
                f"{case['case_id']} "
                "lesion_features 为空。"
            )

        if not case[
            "expected_concepts"
        ]:
            raise ValueError(
                f"{case['case_id']} "
                "expected_concepts 为空。"
            )

        if not case[
            "source_basis"
        ]:
            raise ValueError(
                f"{case['case_id']} "
                "source_basis 为空。"
            )


def write_json_atomic(
    payload: Dict[str, Any],
    file_path: Path,
) -> None:
    """原子方式写入 JSON。"""

    file_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_file = (
        file_path.with_suffix(
            file_path.suffix + ".tmp"
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
        file_path
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "生成任务四 140 条正式测试病例。"
        )
    )

    parser.add_argument(
        "--blueprint",
        type=Path,
        default=DEFAULT_BLUEPRINT_FILE,
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_FILE,
    )

    args = parser.parse_args()

    blueprint_file = (
        args.blueprint
        if args.blueprint.is_absolute()
        else PROJECT_ROOT
        / args.blueprint
    )

    output_file = (
        args.output
        if args.output.is_absolute()
        else PROJECT_ROOT
        / args.output
    )

    try:
        blueprint = load_json(
            blueprint_file
        )

        diseases = blueprint.get(
            "diseases",
            [],
        )

        if not isinstance(
            diseases,
            list,
        ):
            raise ValueError(
                "蓝图 diseases 必须是数组。"
            )

        if len(diseases) != 7:
            raise ValueError(
                f"蓝图疾病数量应为 7，"
                f"实际为 {len(diseases)}。"
            )

        cases = generate_cases(
            diseases
        )

        validate_generation(
            cases
        )

    except (
        FileNotFoundError,
        ValueError,
        TypeError,
        json.JSONDecodeError,
    ) as exc:
        print(
            f"正式病例集生成失败：{exc}"
        )
        return 1

    payload = {
        "dataset_name": (
            "task4_formal_case_dataset_v2"
        ),
        "dataset_version": "2.0",
        "generated_at": (
            current_time()
        ),
        "description": (
            "用于纯 LLM、普通 RAG 和 "
            "KG-RAG 三种方法正式对照实验的"
            "皮肤病辅助诊断合成病例集。"
        ),
        "disease_count": 7,
        "case_type_count": 5,
        "cases_per_disease": 20,
        "total_case_count": 140,
        "data_origin": (
            "synthetic_kg_grounded"
        ),
        "generation_rule": (
            "task4_case_generation_v2"
        ),
        "blueprint": {
            "path": str(
                blueprint_file.relative_to(
                    PROJECT_ROOT
                )
            ),
            "sha256": (
                calculate_sha256(
                    blueprint_file
                )
            ),
        },
        "cases": cases,
    }

    write_json_atomic(
        payload=payload,
        file_path=output_file,
    )

    candidate_distribution = Counter(
        case[
            "candidate_disease"
        ]
        for case in cases
    )

    type_distribution = Counter(
        case[
            "case_type"
        ]
        for case in cases
    )

    print("=" * 72)
    print(
        "任务四正式病例集 V2 生成完成"
    )
    print("=" * 72)
    print(
        f"病例总数：{len(cases)}"
    )
    print(
        f"疾病数量："
        f"{len(candidate_distribution)}"
    )
    print(
        f"病例类型数量："
        f"{len(type_distribution)}"
    )
    print("-" * 72)

    print("疾病分布：")

    for disease_name, count in (
        candidate_distribution.items()
    ):
        print(
            f"  {disease_name}: {count}"
        )

    print("-" * 72)
    print("病例类型分布：")

    for case_type in CASE_TYPES:
        print(
            f"  {case_type}: "
            f"{type_distribution[case_type]}"
        )

    print("-" * 72)
    print(
        f"输出文件：{output_file}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())