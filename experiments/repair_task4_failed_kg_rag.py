"""
Repair failed KG-RAG records in Task 4 batch result files.

Only KG-RAG is rerun. Existing successful LLM and RAG results
are retained without additional model calls.

Examples:

    python experiments/repair_task4_failed_kg_rag.py --plan-only

    python experiments/repair_task4_failed_kg_rag.py
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from experiments.run_three_method_comparison import evaluate_fairness
from rag.baseline_common import result_to_dict
from rag.kg_rag_pipeline import KGRAGPipeline
from rag.llm_client import QwenLLMClient
from rag.schemas import KGRAGResult


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


def current_time() -> str:
    """返回带时区的当前时间。"""

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


def write_json_atomic(
    payload: Dict[str, Any],
    file_path: Path,
) -> None:
    """原子方式写入 JSON，避免中途损坏文件。"""

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


def parse_result(
    payload: Dict[str, Any],
) -> KGRAGResult:
    """兼容 Pydantic V1 和 V2。"""

    if hasattr(
        KGRAGResult,
        "model_validate",
    ):
        return KGRAGResult.model_validate(
            payload
        )

    return KGRAGResult.parse_obj(
        payload
    )


def load_case_mapping(
    case_file: Path,
) -> Dict[str, Dict[str, Any]]:
    """读取固定病例并按 case_id 建立索引。"""

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

    case_mapping: Dict[
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

        if case_id:
            case_mapping[
                case_id
            ] = case

    return case_mapping


def get_method_statuses(
    experiment: Dict[str, Any],
) -> Dict[str, str]:
    """读取三种方法的运行状态。"""

    statuses: Dict[str, str] = {}

    method_results = experiment.get(
        "method_results",
        [],
    )

    if not isinstance(
        method_results,
        list,
    ):
        return statuses

    for record in method_results:
        if not isinstance(record, dict):
            continue

        method = str(
            record.get(
                "method",
                "",
            )
        ).strip()

        result = record.get(
            "result",
            {},
        )

        if (
            method
            and isinstance(result, dict)
        ):
            statuses[method] = str(
                result.get(
                    "run_status",
                    "",
                )
            )

    return statuses


def find_repair_targets(
    case_mapping: Dict[
        str,
        Dict[str, Any],
    ],
    result_directory: Path,
    selected_case_ids: List[str],
) -> List[Dict[str, Any]]:
    """查找仅 KG-RAG 失败的病例。"""

    selected_set = {
        case_id.strip()
        for case_id in selected_case_ids
        if case_id.strip()
    }

    unknown_ids = (
        selected_set
        - set(case_mapping.keys())
    )

    if unknown_ids:
        raise ValueError(
            "指定病例不存在："
            f"{sorted(unknown_ids)}"
        )

    targets: List[
        Dict[str, Any]
    ] = []

    for case_id, case in case_mapping.items():
        if (
            selected_set
            and case_id not in selected_set
        ):
            continue

        result_file = (
            result_directory
            / f"comparison_{case_id}.json"
        )

        if not result_file.exists():
            continue

        experiment = load_json(
            result_file
        )

        statuses = get_method_statuses(
            experiment
        )

        if (
            statuses.get("llm") == "success"
            and statuses.get("rag") == "success"
            and statuses.get("kg_rag") == "failed"
        ):
            targets.append(
                {
                    "case": case,
                    "result_file": result_file,
                    "experiment": experiment,
                }
            )

    return targets


def replace_kg_rag_record(
    experiment: Dict[str, Any],
    new_record: Dict[str, Any],
) -> None:
    """替换原实验中的 KG-RAG 记录。"""

    method_results = experiment.get(
        "method_results",
        [],
    )

    if not isinstance(
        method_results,
        list,
    ):
        raise ValueError(
            "实验结果缺少 method_results 数组。"
        )

    replaced = False

    for index, record in enumerate(
        method_results
    ):
        if (
            isinstance(record, dict)
            and record.get("method")
            == "kg_rag"
        ):
            method_results[index] = (
                new_record
            )
            replaced = True
            break

    if not replaced:
        raise ValueError(
            "实验结果中没有找到 kg_rag 记录。"
        )


def refresh_experiment_metadata(
    experiment: Dict[str, Any],
    repair_wall_time_ms: int,
    previous_error: str,
) -> None:
    """重新计算实验状态、公平性和摘要。"""

    method_records = experiment[
        "method_results"
    ]

    results = [
        parse_result(
            record["result"]
        )
        for record in method_records
    ]

    success_count = sum(
        1
        for result in results
        if result.run_status == "success"
    )

    if success_count == len(results):
        experiment_status = "success"
    elif success_count == 0:
        experiment_status = "failed"
    else:
        experiment_status = (
            "partial_failure"
        )

    experiment[
        "experiment_status"
    ] = experiment_status

    experiment[
        "finished_at"
    ] = current_time()

    experiment[
        "total_wall_time_ms"
    ] = int(
        experiment.get(
            "total_wall_time_ms",
            0,
        )
    ) + repair_wall_time_ms

    experiment[
        "fairness_check"
    ] = evaluate_fairness(
        results
    )

    experiment["summary"] = {
        "method_count": len(results),
        "success_count": success_count,
        "failed_count": (
            len(results)
            - success_count
        ),
        "total_tokens": sum(
            result.token_usage.total_tokens
            for result in results
        ),
    }

    repair_history = experiment.setdefault(
        "repair_history",
        [],
    )

    if not isinstance(
        repair_history,
        list,
    ):
        repair_history = []
        experiment[
            "repair_history"
        ] = repair_history

    repair_history.append(
        {
            "repaired_at": current_time(),
            "method": "kg_rag",
            "previous_error": (
                previous_error
            ),
            "repair_wall_time_ms": (
                repair_wall_time_ms
            ),
            "new_status": (
                experiment_status
            ),
        }
    )


def repair_target(
    target: Dict[str, Any],
    pipeline: KGRAGPipeline,
    top_k: int,
    max_hops: int,
) -> bool:
    """只运行并修复一个病例的 KG-RAG。"""

    case = target["case"]
    experiment = target[
        "experiment"
    ]
    result_file = target[
        "result_file"
    ]

    case_id = str(
        case["case_id"]
    ).strip()

    disease = str(
        case["candidate_disease"]
    ).strip()

    observation = str(
        case["user_observation"]
    ).strip()

    previous_error = ""

    for record in experiment[
        "method_results"
    ]:
        if (
            record.get("method")
            == "kg_rag"
        ):
            result_payload = record.get(
                "result",
                {},
            )

            if isinstance(
                result_payload,
                dict,
            ):
                previous_error = str(
                    result_payload.get(
                        "error_message",
                        "",
                    )
                )

            break

    print("-" * 70)
    print(
        f"正在修复：{case_id} | {disease}"
    )

    started_at = current_time()
    started_counter = (
        time.perf_counter()
    )

    try:
        result = pipeline.run(
            case_id=case_id,
            candidate_disease=disease,
            user_observation=observation,
            top_k=top_k,
            max_hops=max_hops,
        )

    except Exception as exc:
        print(
            "KG-RAG 修复调用失败："
            f"{type(exc).__name__}: {exc}"
        )
        return False

    wall_time_ms = int(
        round(
            (
                time.perf_counter()
                - started_counter
            )
            * 1000
        )
    )

    if result.run_status != "success":
        print(
            "KG-RAG 返回失败状态："
            f"{result.error_message}"
        )
        return False

    backup_timestamp = (
        datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )
    )

    backup_file = (
        result_file.parent
        / (
            f"{result_file.stem}"
            f".before_kg_rag_repair_"
            f"{backup_timestamp}.json"
        )
    )

    shutil.copy2(
        result_file,
        backup_file,
    )

    new_record = {
        "method": "kg_rag",
        "started_at": started_at,
        "wall_time_ms": wall_time_ms,
        "result": result_to_dict(
            result
        ),
    }

    replace_kg_rag_record(
        experiment=experiment,
        new_record=new_record,
    )

    refresh_experiment_metadata(
        experiment=experiment,
        repair_wall_time_ms=(
            wall_time_ms
        ),
        previous_error=(
            previous_error
        ),
    )

    write_json_atomic(
        payload=experiment,
        file_path=result_file,
    )

    print(
        f"修复成功：{case_id}"
    )
    print(
        f"KG-RAG Token："
        f"{result.token_usage.total_tokens}"
    )
    print(
        f"结果文件：{result_file}"
    )
    print(
        f"备份文件：{backup_file}"
    )

    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "仅重新运行任务四中失败的 "
            "KG-RAG，并写回原实验文件。"
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
        "--case-id",
        action="append",
        default=[],
        help=(
            "只修复指定病例；"
            "可重复传入"
        ),
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

    parser.add_argument(
        "--plan-only",
        action="store_true",
    )

    args = parser.parse_args()

    case_file = args.case_file

    if not case_file.is_absolute():
        case_file = (
            PROJECT_ROOT
            / case_file
        )

    result_directory = (
        args.result_dir
    )

    if not result_directory.is_absolute():
        result_directory = (
            PROJECT_ROOT
            / result_directory
        )

    try:
        case_mapping = (
            load_case_mapping(
                case_file
            )
        )

        targets = (
            find_repair_targets(
                case_mapping=(
                    case_mapping
                ),
                result_directory=(
                    result_directory
                ),
                selected_case_ids=(
                    args.case_id
                ),
            )
        )

    except (
        FileNotFoundError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        print(
            f"修复目标读取失败：{exc}"
        )
        return 1

    print("=" * 70)
    print("任务四失败 KG-RAG 修复")
    print("=" * 70)
    print(
        f"待修复病例数量：{len(targets)}"
    )

    for target in targets:
        case = target["case"]

        print(
            f"- {case['case_id']} | "
            f"{case['candidate_disease']}"
        )

    if not targets:
        print(
            "没有发现仅 KG-RAG 失败的病例。"
        )
        return 0

    if args.plan_only:
        print(
            "计划模式未调用大模型。"
        )
        return 0

    shared_client = (
        QwenLLMClient()
    )

    pipeline = KGRAGPipeline(
        client=shared_client
    )

    success_count = 0

    for target in targets:
        if repair_target(
            target=target,
            pipeline=pipeline,
            top_k=args.top_k,
            max_hops=args.max_hops,
        ):
            success_count += 1

    print("=" * 70)
    print("KG-RAG 修复结束")
    print(
        f"成功数量："
        f"{success_count}/{len(targets)}"
    )

    return (
        0
        if success_count == len(targets)
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())