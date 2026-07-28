from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rag.semantic_anchor import SemanticAnchorMapper


TEST_CASES = [
    {
        "case_id": "CASE_001",
        "text": (
            "患者面部出现光亮的珍珠样结节，"
            "表面可见细小血管。"
        ),
        "expected_ids": {
            "LF_010",
            "LF_011",
            "SITE_005",
        },
    },
    {
        "case_id": "CASE_002",
        "text": (
            "皮损形态不对称，边界不规则，"
            "并可见多种颜色。"
        ),
        "expected_ids": {
            "LF_001",
            "LF_002",
            "LF_003",
        },
    },
    {
        "case_id": "CASE_003",
        "text": (
            "皮损整体较对称，边界规则，"
            "颜色相对均匀。"
        ),
        "expected_ids": {
            "LF_006",
            "LF_007",
            "LF_009",
        },
    },
    {
        "case_id": "CASE_004",
        "text": (
            "日光暴露部位出现粗糙并伴有鳞屑的"
            "红色斑片。"
        ),
        "expected_ids": {
            "LF_015",
            "LF_017",
            "SITE_006",
        },
    },
    {
        "case_id": "CASE_005",
        "text": (
            "患者背部出现颜色较深的斑块，"
            "边界欠规则。"
        ),
        "expected_ids": {
            "LF_001",
            "SITE_003",
        },
    },
    {
        "case_id": "CASE_006",
        "text": (
            "皮损颜色均匀，边界规则，"
            "但近期出现轻微增大。"
        ),
        "expected_ids": {
            "LF_004",
            "LF_006",
            "LF_007",
        },
    },
    {
        "case_id": "CASE_007",
        "text": (
            "皮损呈红色，但没有提供形态、"
            "部位和变化情况。"
        ),
        "expected_ids": set(),
    },
]


def main() -> int:
    mapper = SemanticAnchorMapper()

    failed_count = 0

    for test_case in TEST_CASES:
        anchors = mapper.extract(test_case["text"])

        actual_ids = {
            anchor.entity_id
            for anchor in anchors
        }

        expected_ids = test_case["expected_ids"]

        if expected_ids:
            passed = expected_ids.issubset(actual_ids)
        else:
            passed = len(actual_ids) == 0

        status = "通过" if passed else "失败"

        print("=" * 70)
        print(
            f"{test_case['case_id']}：{status}"
        )
        print(
            f"输入：{test_case['text']}"
        )
        print(
            f"预期实体：{sorted(expected_ids)}"
        )
        print(
            f"实际实体：{sorted(actual_ids)}"
        )

        for anchor in anchors:
            print(
                "- "
                f"{anchor.matched_text} "
                f"→ {anchor.entity_name} "
                f"({anchor.entity_id}, "
                f"{anchor.entity_type}, "
                f"{anchor.confidence})"
            )

        if not passed:
            failed_count += 1

    print("=" * 70)

    if failed_count:
        print(
            f"语义锚点验证未通过："
            f"{failed_count} 个样例失败。"
        )
        return 1

    print(
        "语义锚点验证通过："
        f"{len(TEST_CASES)} 个样例全部通过。"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())