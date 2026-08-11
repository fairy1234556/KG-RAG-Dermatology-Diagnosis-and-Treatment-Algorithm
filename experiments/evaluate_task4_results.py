"""
Evaluate Task 4 three-method comparison results.

This script does not call the LLM API.

It calculates:

1. Run success rate.
2. Expected concept coverage.
3. Source traceability.
4. Evidence-path traceability.
5. Evidence-path completeness.
6. Safety-information completeness.
7. Token usage.
8. Response latency.
9. Coverage efficiency per 1000 tokens.

Run:

    python experiments/evaluate_task4_results.py
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


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

DEFAULT_OUTPUT_DIRECTORY = (
    PROJECT_ROOT
    / "experiments"
    / "results"
    / "task4_metrics_v1"
)

METHOD_ORDER = [
    "llm",
    "rag",
    "kg_rag",
]

CLAIM_FIELDS = [
    "observation_match",
    "supporting_evidence",
    "differential_diagnosis",
    "risk_warning",
    "medical_advice",
    "evidence_gap",
]

CONCEPT_EVALUATION_FIELDS = [
    "observation_match",
    "supporting_evidence",
]

SAFETY_CRITERIA = [
    "disclaimer",
    "risk_warning",
    "medical_advice",
    "evidence_gap",
]


# 自动匹配使用的同义表达。
# 仅用于任务四的词法覆盖率计算，不改变病例集和模型输入。
CONCEPT_ALIASES: Dict[str, List[str]] = {
    "珍珠样结节": [
        "珍珠样结节",
        "珍珠色结节",
        "珍珠样丘疹",
        "光亮结节",
    ],
    "表面毛细血管扩张": [
        "表面毛细血管扩张",
        "毛细血管扩张",
        "细小血管",
        "表面血管",
        "血管穿过",
    ],
    "面部": [
        "面部",
        "头面部",
        "脸部",
    ],
    "不对称": [
        "不对称",
        "形态不对称",
    ],
    "边界不规则": [
        "边界不规则",
        "边缘不规则",
        "不规则边界",
    ],
    "多种颜色": [
        "多种颜色",
        "颜色深浅不一",
        "颜色不均",
        "色泽不均",
        "多色",
    ],
    "近期变化": [
        "近期变化",
        "近期有增大趋势",
        "近期增大",
        "增大趋势",
        "发生变化",
    ],
    "棕色": [
        "棕色",
        "褐色",
        "棕褐色",
    ],
    "形状规则": [
        "形状规则",
        "形状较规则",
        "规则形状",
        "形态规则",
    ],
    "边界清楚": [
        "边界清楚",
        "边界清晰",
        "界限清楚",
        "界限清晰",
    ],
    "长期稳定": [
        "长期稳定",
        "长期存在",
        "近期无明显变化",
        "无明显变化",
        "保持稳定",
    ],
    "日晒部位": [
        "日晒部位",
        "日光暴露部位",
        "日光暴露区域",
        "曝光部位",
    ],
    "粗糙": [
        "粗糙",
        "表面粗糙",
    ],
    "红色斑片": [
        "红色斑片",
        "红色鳞屑性斑片",
        "红斑",
    ],
    "鳞屑": [
        "鳞屑",
        "鳞屑性",
        "脱屑",
    ],
    "角化": [
        "角化",
        "角化性",
        "角质",
    ],
    "棕褐色": [
        "棕褐色",
        "褐色",
        "棕色",
    ],
    "隆起性斑块": [
        "隆起性斑块",
        "隆起斑块",
        "丘疹或斑块",
        "隆起性皮损",
    ],
    "表面粗糙": [
        "表面粗糙",
        "粗糙表面",
        "蜡样或疣状表面",
        "疣状表面",
    ],
    "贴附样外观": [
        "贴附样外观",
        "贴附样",
        "贴在皮肤上",
        "贴在皮肤表面",
        "贴附在皮肤表面",
    ],
    "小腿": [
        "小腿",
        "下肢",
    ],
    "质地较硬": [
        "质地较硬",
        "质地硬",
        "坚实",
        "较硬",
    ],
    "棕褐色结节": [
        "棕褐色结节",
        "棕褐色小结节",
        "褐色结节",
    ],
    "中央凹陷": [
        "中央凹陷",
        "凹陷征",
        "捏压凹陷",
        "中央可出现凹陷",
    ],
    "鲜红色": [
        "鲜红色",
        "红色",
    ],
    "圆形丘疹": [
        "圆形丘疹",
        "圆形小丘疹",
        "红色丘疹",
        "丘疹",
    ],
    "表面光滑": [
        "表面光滑",
        "光滑表面",
        "光滑",
    ],
    "按压褪色": [
        "按压褪色",
        "按压后褪色",
        "按压后颜色可暂时变浅",
        "按压后颜色变浅",
        "压之褪色",
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


def load_json(file_path: Path) -> Dict[str, Any]:
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
    """写入格式化 JSON。"""

    file_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with file_path.open(
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


def write_csv(
    rows: List[Dict[str, Any]],
    file_path: Path,
) -> None:
    """写入 UTF-8 BOM CSV，便于 Excel 打开。"""

    if not rows:
        raise ValueError(
            f"没有可写入 CSV 的数据：{file_path}"
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
    """统一文本，用于词法匹配。"""

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


def ensure_string_list(
    value: Any,
) -> List[str]:
    """将字段安全转换为字符串列表。"""

    if value is None:
        return []

    if isinstance(value, str):
        cleaned = value.strip()
        return [cleaned] if cleaned else []

    if not isinstance(value, list):
        return []

    result: List[str] = []

    for item in value:
        if not isinstance(item, str):
            continue

        cleaned = item.strip()

        if cleaned:
            result.append(cleaned)

    return result


def unique_non_empty(
    values: Iterable[str],
) -> List[str]:
    """保留顺序并去除空值和重复值。"""

    result: List[str] = []

    for value in values:
        cleaned = str(
            value or ""
        ).strip()

        if (
            cleaned
            and cleaned not in result
        ):
            result.append(cleaned)

    return result


def safe_ratio(
    numerator: float,
    denominator: float,
) -> float:
    """安全计算比例。"""

    if denominator <= 0:
        return 0.0

    return round(
        numerator / denominator,
        6,
    )


def average(
    values: Sequence[float],
) -> float:
    """计算平均值，空序列返回 0。"""

    if not values:
        return 0.0

    return round(
        statistics.mean(values),
        6,
    )


def median(
    values: Sequence[float],
) -> float:
    """计算中位数，空序列返回 0。"""

    if not values:
        return 0.0

    return round(
        statistics.median(values),
        6,
    )


def get_concept_forms(
    concept: str,
) -> List[str]:
    """取得概念及其同义表达。"""

    configured_aliases = (
        CONCEPT_ALIASES.get(
            concept,
            [],
        )
    )

    return unique_non_empty(
        [concept] + configured_aliases
    )


def concept_is_matched(
    concept: str,
    evaluation_text: str,
) -> bool:
    """检查概念或同义表达是否出现在输出文本中。"""

    normalized_output = normalize_text(
        evaluation_text
    )

    for form in get_concept_forms(
        concept
    ):
        normalized_form = normalize_text(
            form
        )

        if (
            normalized_form
            and normalized_form
            in normalized_output
        ):
            return True

    return False


def build_concept_evaluation_text(
    result: Dict[str, Any],
) -> str:
    """
    构建观察概念覆盖率的评价文本。

    为保证三种方法公平，只使用模型生成的：

    - observation_match；
    - supporting_evidence。

    不使用 KG-RAG 程序注入的 evidence_paths。
    """

    texts: List[str] = []

    for field_name in (
        CONCEPT_EVALUATION_FIELDS
    ):
        texts.extend(
            ensure_string_list(
                result.get(
                    field_name,
                    [],
                )
            )
        )

    return "\n".join(texts)


def evaluate_expected_concepts(
    expected_concepts: List[str],
    result: Dict[str, Any],
) -> Dict[str, Any]:
    """计算单个结果的观察概念覆盖率。"""

    evaluation_text = (
        build_concept_evaluation_text(
            result
        )
    )

    matched_concepts: List[str] = []
    missing_concepts: List[str] = []

    for concept in expected_concepts:
        if concept_is_matched(
            concept,
            evaluation_text,
        ):
            matched_concepts.append(
                concept
            )
        else:
            missing_concepts.append(
                concept
            )

    concept_count = len(
        expected_concepts
    )

    matched_count = len(
        matched_concepts
    )

    return {
        "expected_concept_count": (
            concept_count
        ),
        "matched_concept_count": (
            matched_count
        ),
        "expected_concept_coverage": (
            safe_ratio(
                matched_count,
                concept_count,
            )
        ),
        "matched_concepts": (
            matched_concepts
        ),
        "missing_concepts": (
            missing_concepts
        ),
    }


def evaluate_safety_completeness(
    result: Dict[str, Any],
) -> float:
    """计算安全信息字段的完整率。"""

    completed_count = 0

    disclaimer = str(
        result.get(
            "disclaimer",
            "",
        )
    ).strip()

    if disclaimer:
        completed_count += 1

    for field_name in [
        "risk_warning",
        "medical_advice",
        "evidence_gap",
    ]:
        values = ensure_string_list(
            result.get(
                field_name,
                [],
            )
        )

        if values:
            completed_count += 1

    return safe_ratio(
        completed_count,
        len(SAFETY_CRITERIA),
    )


def evaluate_evidence_paths(
    result: Dict[str, Any],
) -> Dict[str, Any]:
    """计算图谱证据链数量和字段完整率。"""

    paths = result.get(
        "evidence_paths",
        [],
    )

    if not isinstance(paths, list):
        paths = []

    required_fields = [
        "head_entity",
        "relation",
        "tail_entity",
        "evidence_text",
        "source_id",
        "source_name",
        "score",
    ]

    complete_count = 0

    for path in paths:
        if not isinstance(path, dict):
            continue

        path_complete = True

        for field_name in required_fields:
            value = path.get(
                field_name
            )

            if field_name == "score":
                if value is None:
                    path_complete = False
                    break

            else:
                if not str(
                    value or ""
                ).strip():
                    path_complete = False
                    break

        if path_complete:
            complete_count += 1

    path_count = len(paths)

    completeness: Optional[float]

    if path_count > 0:
        completeness = safe_ratio(
            complete_count,
            path_count,
        )
    else:
        completeness = None

    return {
        "evidence_path_count": (
            path_count
        ),
        "evidence_path_traceable": (
            int(path_count > 0)
        ),
        "complete_evidence_path_count": (
            complete_count
        ),
        "evidence_path_completeness": (
            completeness
        ),
    }


def count_generated_claims(
    result: Dict[str, Any],
) -> int:
    """统计结构化回答中生成的条目数量。"""

    return sum(
        len(
            ensure_string_list(
                result.get(
                    field_name,
                    [],
                )
            )
        )
        for field_name in CLAIM_FIELDS
    )


def find_method_record(
    experiment: Dict[str, Any],
    method_name: str,
) -> Dict[str, Any]:
    """查找指定实验方法的结果记录。"""

    records = experiment.get(
        "method_results",
        [],
    )

    if not isinstance(records, list):
        raise ValueError(
            "实验文件中的 method_results 必须是数组。"
        )

    matches = [
        record
        for record in records
        if (
            isinstance(record, dict)
            and record.get("method")
            == method_name
        )
    ]

    if len(matches) != 1:
        raise ValueError(
            f"方法 {method_name} 的结果数量不为 1，"
            f"实际为 {len(matches)}。"
        )

    return matches[0]


def evaluate_single_result(
    case: Dict[str, Any],
    method_record: Dict[str, Any],
) -> Dict[str, Any]:
    """计算单病例、单方法的指标。"""

    result = method_record.get(
        "result",
        {},
    )

    if not isinstance(result, dict):
        raise ValueError(
            "方法结果中的 result 必须是对象。"
        )

    expected_concepts = [
        str(value).strip()
        for value in case.get(
            "expected_concepts",
            [],
        )
        if str(value).strip()
    ]

    concept_metrics = (
        evaluate_expected_concepts(
            expected_concepts=(
                expected_concepts
            ),
            result=result,
        )
    )

    path_metrics = (
        evaluate_evidence_paths(
            result
        )
    )

    sources = unique_non_empty(
        ensure_string_list(
            result.get(
                "sources",
                [],
            )
        )
    )

    token_usage = result.get(
        "token_usage",
        {},
    )

    if not isinstance(
        token_usage,
        dict,
    ):
        token_usage = {}

    total_tokens = int(
        token_usage.get(
            "total_tokens",
            0,
        )
        or 0
    )

    concept_coverage = float(
        concept_metrics[
            "expected_concept_coverage"
        ]
    )

    coverage_per_1000_tokens = 0.0

    if total_tokens > 0:
        coverage_per_1000_tokens = round(
            concept_coverage
            * 1000
            / total_tokens,
            6,
        )

    return {
        "case_id": str(
            case["case_id"]
        ).strip(),
        "candidate_disease": str(
            case["candidate_disease"]
        ).strip(),
        "case_type": str(
            case.get(
                "case_type",
                "",
            )
        ).strip(),
        "method": str(
            method_record.get(
                "method",
                "",
            )
        ).strip(),
        "run_status": str(
            result.get(
                "run_status",
                "",
            )
        ).strip(),
        "expected_concept_count": (
            concept_metrics[
                "expected_concept_count"
            ]
        ),
        "matched_concept_count": (
            concept_metrics[
                "matched_concept_count"
            ]
        ),
        "expected_concept_coverage": (
            concept_coverage
        ),
        "matched_concepts": "；".join(
            concept_metrics[
                "matched_concepts"
            ]
        ),
        "missing_concepts": "；".join(
            concept_metrics[
                "missing_concepts"
            ]
        ),
        "source_traceable": int(
            bool(sources)
        ),
        "source_count": len(
            sources
        ),
        "sources": "；".join(
            sources
        ),
        "evidence_path_traceable": (
            path_metrics[
                "evidence_path_traceable"
            ]
        ),
        "evidence_path_count": (
            path_metrics[
                "evidence_path_count"
            ]
        ),
        "complete_evidence_path_count": (
            path_metrics[
                "complete_evidence_path_count"
            ]
        ),
        "evidence_path_completeness": (
            path_metrics[
                "evidence_path_completeness"
            ]
        ),
        "safety_completeness": (
            evaluate_safety_completeness(
                result
            )
        ),
        "generated_claim_count": (
            count_generated_claims(
                result
            )
        ),
        "prompt_tokens": int(
            token_usage.get(
                "prompt_tokens",
                0,
            )
            or 0
        ),
        "completion_tokens": int(
            token_usage.get(
                "completion_tokens",
                0,
            )
            or 0
        ),
        "total_tokens": (
            total_tokens
        ),
        "response_time_ms": int(
            result.get(
                "response_time_ms",
                0,
            )
            or 0
        ),
        "wall_time_ms": int(
            method_record.get(
                "wall_time_ms",
                0,
            )
            or 0
        ),
        "coverage_per_1000_tokens": (
            coverage_per_1000_tokens
        ),
        "model_name": str(
            result.get(
                "model_name",
                "",
            )
        ).strip(),
        "prompt_version": str(
            result.get(
                "prompt_version",
                "",
            )
        ).strip(),
    }


def aggregate_method_rows(
    method_name: str,
    rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """按实验方法汇总指标。"""

    method_rows = [
        row
        for row in rows
        if row["method"] == method_name
    ]

    successful_rows = [
        row
        for row in method_rows
        if row["run_status"]
        == "success"
    ]

    path_completeness_values = [
        float(
            row[
                "evidence_path_completeness"
            ]
        )
        for row in successful_rows
        if row[
            "evidence_path_completeness"
        ] is not None
    ]

    response_times = [
        float(
            row["response_time_ms"]
        )
        for row in successful_rows
    ]

    wall_times = [
        float(
            row["wall_time_ms"]
        )
        for row in successful_rows
    ]

    return {
        "method": method_name,
        "case_count": len(
            method_rows
        ),
        "successful_case_count": len(
            successful_rows
        ),
        "run_success_rate": safe_ratio(
            len(successful_rows),
            len(method_rows),
        ),
        "average_expected_concept_coverage": (
            average(
                [
                    float(
                        row[
                            "expected_concept_coverage"
                        ]
                    )
                    for row in successful_rows
                ]
            )
        ),
        "source_traceability_rate": (
            average(
                [
                    float(
                        row[
                            "source_traceable"
                        ]
                    )
                    for row in successful_rows
                ]
            )
        ),
        "evidence_path_traceability_rate": (
            average(
                [
                    float(
                        row[
                            "evidence_path_traceable"
                        ]
                    )
                    for row in successful_rows
                ]
            )
        ),
        "average_source_count": average(
            [
                float(
                    row["source_count"]
                )
                for row in successful_rows
            ]
        ),
        "average_evidence_path_count": (
            average(
                [
                    float(
                        row[
                            "evidence_path_count"
                        ]
                    )
                    for row in successful_rows
                ]
            )
        ),
        "average_evidence_path_completeness": (
            average(
                path_completeness_values
            )
            if path_completeness_values
            else None
        ),
        "average_safety_completeness": (
            average(
                [
                    float(
                        row[
                            "safety_completeness"
                        ]
                    )
                    for row in successful_rows
                ]
            )
        ),
        "average_generated_claim_count": (
            average(
                [
                    float(
                        row[
                            "generated_claim_count"
                        ]
                    )
                    for row in successful_rows
                ]
            )
        ),
        "average_prompt_tokens": average(
            [
                float(
                    row["prompt_tokens"]
                )
                for row in successful_rows
            ]
        ),
        "average_completion_tokens": (
            average(
                [
                    float(
                        row[
                            "completion_tokens"
                        ]
                    )
                    for row in successful_rows
                ]
            )
        ),
        "average_total_tokens": average(
            [
                float(
                    row["total_tokens"]
                )
                for row in successful_rows
            ]
        ),
        "average_response_time_ms": (
            average(
                response_times
            )
        ),
        "median_response_time_ms": (
            median(
                response_times
            )
        ),
        "average_wall_time_ms": (
            average(
                wall_times
            )
        ),
        "average_coverage_per_1000_tokens": (
            average(
                [
                    float(
                        row[
                            "coverage_per_1000_tokens"
                        ]
                    )
                    for row in successful_rows
                ]
            )
        ),
    }


def format_percentage(
    value: Any,
) -> str:
    """将 0～1 比例格式化为百分数。"""

    if value is None:
        return "不适用"

    return (
        f"{float(value) * 100:.2f}%"
    )


def build_markdown_report(
    dataset_name: str,
    per_case_rows: List[Dict[str, Any]],
    method_summaries: List[Dict[str, Any]],
) -> str:
    """生成便于论文整理的 Markdown 摘要。"""

    lines = [
        "# 任务四三方法对照实验自动指标报告",
        "",
        f"- 数据集：`{dataset_name}`",
        f"- 病例数量：{len(per_case_rows) // 3}",
        f"- 方法数量：3",
        f"- 结果数量：{len(per_case_rows)}",
        f"- 生成时间：{current_time()}",
        "",
        "## 一、方法汇总",
        "",
        (
            "| 方法 | 成功率 | 观察概念覆盖率 | "
            "来源可追溯率 | 证据链可追溯率 | "
            "平均 Token | 平均响应时间/ms |"
        ),
        (
            "|---|---:|---:|---:|---:|---:|---:|"
        ),
    ]

    for summary in method_summaries:
        lines.append(
            "| "
            f"{summary['method']} | "
            f"{format_percentage(summary['run_success_rate'])} | "
            f"{format_percentage(summary['average_expected_concept_coverage'])} | "
            f"{format_percentage(summary['source_traceability_rate'])} | "
            f"{format_percentage(summary['evidence_path_traceability_rate'])} | "
            f"{summary['average_total_tokens']:.2f} | "
            f"{summary['average_response_time_ms']:.2f} |"
        )

    lines.extend(
        [
            "",
            "## 二、指标解释",
            "",
            (
                "1. **观察概念覆盖率**：仅在模型生成的 "
                "`observation_match` 和 "
                "`supporting_evidence` 中匹配病例预设概念及其同义表达，"
                "不读取程序注入的图谱证据链。"
            ),
            (
                "2. **来源可追溯率**：成功结果中 `sources` 非空的病例比例。"
            ),
            (
                "3. **证据链可追溯率**：成功结果中 "
                "`evidence_paths` 非空的病例比例。"
            ),
            (
                "4. **安全信息完整率**：免责声明、风险提示、"
                "医疗建议和证据缺口四项的完成比例。"
            ),
            (
                "5. 自动概念覆盖率属于词法代理指标，"
                "不能替代人工医学正确性评价和证据一致性评价。"
            ),
            "",
            "## 三、后续评价",
            "",
            (
                "下一阶段需要进行生成陈述与检索证据之间的"
                "逐条一致性校验，并增加人工评分。"
            ),
            "",
        ]
    )

    return "\n".join(
        lines
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "计算任务四三方法实验的自动评价指标。"
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

    output_directory = resolve_path(
        args.output_dir
    )

    try:
        dataset = load_json(
            case_file
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

        per_case_rows: List[
            Dict[str, Any]
        ] = []

        for case in cases:
            if not isinstance(
                case,
                dict,
            ):
                raise ValueError(
                    "病例记录必须是对象。"
                )

            case_id = str(
                case.get(
                    "case_id",
                    "",
                )
            ).strip()

            result_file = (
                result_directory
                / f"comparison_{case_id}.json"
            )

            experiment = load_json(
                result_file
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

                row = (
                    evaluate_single_result(
                        case=case,
                        method_record=(
                            method_record
                        ),
                    )
                )

                per_case_rows.append(
                    row
                )

        method_summaries = [
            aggregate_method_rows(
                method_name,
                per_case_rows,
            )
            for method_name in METHOD_ORDER
        ]

    except (
        FileNotFoundError,
        ValueError,
        TypeError,
        json.JSONDecodeError,
    ) as exc:
        print(
            f"任务四指标计算失败：{exc}"
        )
        return 1

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    per_case_csv = (
        output_directory
        / "task4_per_case_metrics.csv"
    )

    method_summary_csv = (
        output_directory
        / "task4_method_summary.csv"
    )

    report_json = (
        output_directory
        / "task4_metrics_report.json"
    )

    report_markdown = (
        output_directory
        / "task4_metrics_report.md"
    )

    report_payload = {
        "report_name": (
            "task4_three_method_metrics_v1"
        ),
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
        "case_count": len(cases),
        "method_count": len(
            METHOD_ORDER
        ),
        "result_count": len(
            per_case_rows
        ),
        "metric_definitions": {
            "expected_concept_coverage": (
                "在 observation_match 和 "
                "supporting_evidence 中匹配"
                "预设观察概念及同义表达的比例。"
            ),
            "source_traceability_rate": (
                "成功结果中 sources 非空的比例。"
            ),
            "evidence_path_traceability_rate": (
                "成功结果中 evidence_paths "
                "非空的比例。"
            ),
            "evidence_path_completeness": (
                "证据链中头实体、关系、尾实体、"
                "证据文本、来源编号、来源名称和"
                "得分均完整的路径比例。"
            ),
            "safety_completeness": (
                "免责声明、风险提示、医疗建议和"
                "证据缺口四项的完成比例。"
            ),
        },
        "method_summary": (
            method_summaries
        ),
        "per_case_metrics": (
            per_case_rows
        ),
    }

    write_csv(
        per_case_rows,
        per_case_csv,
    )

    write_csv(
        method_summaries,
        method_summary_csv,
    )

    write_json(
        report_payload,
        report_json,
    )

    markdown_content = (
        build_markdown_report(
            dataset_name=str(
                dataset.get(
                    "dataset_name",
                    "",
                )
            ),
            per_case_rows=(
                per_case_rows
            ),
            method_summaries=(
                method_summaries
            ),
        )
    )

    report_markdown.write_text(
        markdown_content,
        encoding="utf-8",
    )

    failed_rows = [
        row
        for row in per_case_rows
        if row["run_status"]
        != "success"
    ]

    print("=" * 70)
    print("任务四自动指标计算完成")
    print("=" * 70)
    print(
        f"病例数量：{len(cases)}"
    )
    print(
        f"结果数量：{len(per_case_rows)}"
    )
    print(
        f"失败结果数量：{len(failed_rows)}"
    )
    print("-" * 70)

    for summary in method_summaries:
        print(
            f"{summary['method']} | "
            f"成功率="
            f"{format_percentage(summary['run_success_rate'])} | "
            f"概念覆盖率="
            f"{format_percentage(summary['average_expected_concept_coverage'])} | "
            f"来源可追溯率="
            f"{format_percentage(summary['source_traceability_rate'])} | "
            f"证据链可追溯率="
            f"{format_percentage(summary['evidence_path_traceability_rate'])} | "
            f"平均Token="
            f"{summary['average_total_tokens']:.2f} | "
            f"平均响应时间="
            f"{summary['average_response_time_ms']:.2f}ms"
        )

    print("-" * 70)
    print(
        f"病例级指标：{per_case_csv}"
    )
    print(
        f"方法汇总指标：{method_summary_csv}"
    )
    print(
        f"完整 JSON 报告：{report_json}"
    )
    print(
        f"Markdown 报告：{report_markdown}"
    )

    return 0 if not failed_rows else 1


if __name__ == "__main__":
    raise SystemExit(main())