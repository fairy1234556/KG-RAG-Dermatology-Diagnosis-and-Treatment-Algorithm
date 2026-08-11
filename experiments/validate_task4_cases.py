"""
Validate the fixed Task 4 comparison case set.

Run:

    python experiments/validate_task4_cases.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]

CASE_FILE = (
    PROJECT_ROOT
    / "experiments"
    / "cases"
    / "task4_cases_v1.json"
)

EXPECTED_DISEASES = {
    "基底细胞癌",
    "黑色素瘤",
    "黑色素细胞痣",
    "光化性角化病/表皮内癌",
    "良性角化性病变",
    "皮肤纤维瘤",
    "血管性病变",
}


def load_case_dataset() -> Dict[str, Any]:
    if not CASE_FILE.exists():
        raise FileNotFoundError(
            f"找不到病例集：{CASE_FILE}"
        )

    with CASE_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        payload = json.load(file)

    if not isinstance(payload, dict):
        raise ValueError(
            "病例集根节点必须是 JSON 对象。"
        )

    return payload


def validate_dataset(
    payload: Dict[str, Any],
) -> List[str]:
    errors: List[str] = []

    cases = payload.get("cases")

    if not isinstance(cases, list):
        return [
            "cases 必须是数组。"
        ]

    declared_count = payload.get(
        "case_count"
    )

    if declared_count != len(cases):
        errors.append(
            "case_count 与实际病例数量不一致："
            f"{declared_count} != {len(cases)}"
        )

    case_ids: List[str] = []
    diseases: List[str] = []

    required_fields = {
        "case_id",
        "candidate_disease",
        "user_observation",
        "expected_concepts",
        "case_type",
    }

    for index, case in enumerate(
        cases,
        start=1,
    ):
        if not isinstance(case, dict):
            errors.append(
                f"第 {index} 个病例不是 JSON 对象。"
            )
            continue

        missing_fields = (
            required_fields
            - set(case.keys())
        )

        if missing_fields:
            errors.append(
                f"第 {index} 个病例缺少字段："
                f"{sorted(missing_fields)}"
            )
            continue

        case_id = str(
            case["case_id"]
        ).strip()

        disease = str(
            case["candidate_disease"]
        ).strip()

        observation = str(
            case["user_observation"]
        ).strip()

        concepts = case[
            "expected_concepts"
        ]

        if not case_id:
            errors.append(
                f"第 {index} 个病例 case_id 为空。"
            )

        if not disease:
            errors.append(
                f"第 {index} 个病例候选疾病为空。"
            )

        if not observation:
            errors.append(
                f"第 {index} 个病例观察文本为空。"
            )

        if (
            not isinstance(concepts, list)
            or not concepts
        ):
            errors.append(
                f"第 {index} 个病例 expected_concepts "
                "必须是非空数组。"
            )

        elif not all(
            isinstance(value, str)
            and value.strip()
            for value in concepts
        ):
            errors.append(
                f"第 {index} 个病例 expected_concepts "
                "包含空值或非字符串。"
            )

        case_ids.append(case_id)
        diseases.append(disease)

    duplicate_ids = sorted(
        {
            case_id
            for case_id in case_ids
            if case_ids.count(case_id) > 1
        }
    )

    if duplicate_ids:
        errors.append(
            "存在重复 case_id："
            f"{duplicate_ids}"
        )

    actual_diseases = set(
        diseases
    )

    missing_diseases = (
        EXPECTED_DISEASES
        - actual_diseases
    )

    unexpected_diseases = (
        actual_diseases
        - EXPECTED_DISEASES
    )

    if missing_diseases:
        errors.append(
            "缺少疾病类别："
            f"{sorted(missing_diseases)}"
        )

    if unexpected_diseases:
        errors.append(
            "存在未计划疾病类别："
            f"{sorted(unexpected_diseases)}"
        )

    if len(cases) != 7:
        errors.append(
            "任务四第一版病例集应包含 7 个病例，"
            f"当前为 {len(cases)}。"
        )

    return errors


def main() -> int:
    try:
        payload = load_case_dataset()
        errors = validate_dataset(
            payload
        )

    except (
        FileNotFoundError,
        json.JSONDecodeError,
        ValueError,
    ) as exc:
        print(
            f"任务四病例集验证失败：{exc}"
        )
        return 1

    cases = payload["cases"]

    print("=" * 70)
    print("任务四固定病例集验证")
    print("=" * 70)
    print(
        f"数据集名称："
        f"{payload.get('dataset_name', '')}"
    )
    print(
        f"数据集版本："
        f"{payload.get('dataset_version', '')}"
    )
    print(f"病例数量：{len(cases)}")
    print(
        "疾病类别："
        f"{[case['candidate_disease'] for case in cases]}"
    )

    if errors:
        print("-" * 70)

        for error in errors:
            print(f"错误：{error}")

        print("-" * 70)
        print(
            f"病例集验证未通过："
            f"共发现 {len(errors)} 个问题。"
        )
        return 1

    print("-" * 70)
    print(
        "任务四病例集验证通过："
        "7 个疾病类别均已覆盖。"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())