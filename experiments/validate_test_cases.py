from __future__ import annotations

import csv
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_CASE_FILE = PROJECT_ROOT / "experiments" / "data" / "august_test_cases.csv"

REQUIRED_COLUMNS = {
    "case_id",
    "true_label",
    "candidate_disease",
    "observation_text",
    "lesion_features",
    "anatomical_site",
    "symptoms",
    "difficulty_level",
    "case_type",
    "source_type",
    "notes",
}

VALID_LABELS = {
    "mel",
    "nv",
    "bcc",
    "akiec",
    "bkl",
    "df",
    "vasc",
}

VALID_DIFFICULTIES = {
    "easy",
    "medium",
    "hard",
}

VALID_CASE_TYPES = {
    "supportive",
    "partial_support",
    "conflicting",
    "insufficient",
}


def validate_test_cases() -> list[str]:
    errors: list[str] = []

    if not TEST_CASE_FILE.exists():
        return [f"测试样例文件不存在：{TEST_CASE_FILE}"]

    with TEST_CASE_FILE.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        if reader.fieldnames is None:
            return ["CSV 文件没有表头。"]

        actual_columns = set(reader.fieldnames)
        missing_columns = REQUIRED_COLUMNS - actual_columns

        if missing_columns:
            errors.append(
                f"缺少字段：{', '.join(sorted(missing_columns))}"
            )
            return errors

        seen_case_ids: set[str] = set()

        for row_number, row in enumerate(reader, start=2):
            case_id = row["case_id"].strip()
            true_label = row["true_label"].strip()
            candidate_disease = row["candidate_disease"].strip()
            observation_text = row["observation_text"].strip()
            difficulty_level = row["difficulty_level"].strip()
            case_type = row["case_type"].strip()

            if not case_id:
                errors.append(f"第 {row_number} 行 case_id 为空。")
            elif case_id in seen_case_ids:
                errors.append(
                    f"第 {row_number} 行 case_id 重复：{case_id}"
                )
            else:
                seen_case_ids.add(case_id)

            if true_label not in VALID_LABELS:
                errors.append(
                    f"第 {row_number} 行 true_label 非法：{true_label}"
                )

            if not candidate_disease:
                errors.append(
                    f"第 {row_number} 行 candidate_disease 为空。"
                )

            if not observation_text:
                errors.append(
                    f"第 {row_number} 行 observation_text 为空。"
                )

            if difficulty_level not in VALID_DIFFICULTIES:
                errors.append(
                    f"第 {row_number} 行 difficulty_level 非法："
                    f"{difficulty_level}"
                )

            if case_type not in VALID_CASE_TYPES:
                errors.append(
                    f"第 {row_number} 行 case_type 非法：{case_type}"
                )

    return errors


def main() -> int:
    errors = validate_test_cases()

    if errors:
        print("测试样例检查未通过：")
        for error in errors:
            print(f"- {error}")
        return 1

    print("测试样例检查通过。")
    print(f"文件位置：{TEST_CASE_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())