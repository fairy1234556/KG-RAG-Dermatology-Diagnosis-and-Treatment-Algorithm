"""
Batch runner for Task 4 three-method comparison experiments.

For every case, run:

1. Pure LLM baseline.
2. Ordinary text RAG baseline.
3. KG-RAG pipeline.

Features:

- one result file per case;
- checkpoint and resume;
- failed-case retry;
- stable output file names;
- incremental batch manifest;
- plan-only mode.

Examples:

    python experiments/run_task4_batch.py --plan-only

    python experiments/run_task4_batch.py --limit 1

    python experiments/run_task4_batch.py
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_CASE_FILE = (
    PROJECT_ROOT
    / "experiments"
    / "cases"
    / "task4_cases_v1.json"
)

DEFAULT_OUTPUT_DIRECTORY = (
    PROJECT_ROOT
    / "experiments"
    / "results"
    / "task4_batch_v1"
)

COMPARISON_RUNNER = (
    PROJECT_ROOT
    / "experiments"
    / "run_three_method_comparison.py"
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


def sanitize_filename(value: str) -> str:
    """将病例编号转换成安全文件名。"""

    cleaned = re.sub(
        r"[^A-Za-z0-9._-]+",
        "_",
        (value or "").strip(),
    )

    cleaned = cleaned.strip(
        "._-"
    )

    return cleaned or "case"


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
    """写入格式化 JSON 文件。"""

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


def load_cases(
    case_file: Path,
) -> Dict[str, Any]:
    """读取并验证批量病例集。"""

    payload = load_json(
        case_file
    )

    cases = payload.get(
        "cases"
    )

    if not isinstance(cases, list):
        raise ValueError(
            "病例集中的 cases 必须是数组。"
        )

    if not cases:
        raise ValueError(
            "病例集不能为空。"
        )

    required_fields = {
        "case_id",
        "candidate_disease",
        "user_observation",
    }

    case_ids: List[str] = []

    for index, case in enumerate(
        cases,
        start=1,
    ):
        if not isinstance(case, dict):
            raise ValueError(
                f"第 {index} 个病例必须是 JSON 对象。"
            )

        missing_fields = (
            required_fields
            - set(case.keys())
        )

        if missing_fields:
            raise ValueError(
                f"第 {index} 个病例缺少字段："
                f"{sorted(missing_fields)}"
            )

        case_id = str(
            case["case_id"]
        ).strip()

        disease = str(
            case["candidate_disease"]
        ).strip()

        observation = str(
            case["user_observation"]
        ).strip()

        if not case_id:
            raise ValueError(
                f"第 {index} 个病例 case_id 为空。"
            )

        if not disease:
            raise ValueError(
                f"第 {index} 个病例候选疾病为空。"
            )

        if not observation:
            raise ValueError(
                f"第 {index} 个病例观察文本为空。"
            )

        case_ids.append(
            case_id
        )

    duplicate_ids = sorted(
        {
            case_id
            for case_id in case_ids
            if case_ids.count(case_id) > 1
        }
    )

    if duplicate_ids:
        raise ValueError(
            "病例集存在重复 case_id："
            f"{duplicate_ids}"
        )

    return payload


def select_cases(
    cases: List[Dict[str, Any]],
    selected_case_ids: Optional[List[str]],
    limit: Optional[int],
) -> List[Dict[str, Any]]:
    """根据病例编号和 limit 筛选病例。"""

    selected = list(
        cases
    )

    if selected_case_ids:
        requested_ids = {
            case_id.strip()
            for case_id in selected_case_ids
            if case_id.strip()
        }

        available_ids = {
            str(case["case_id"]).strip()
            for case in cases
        }

        unknown_ids = sorted(
            requested_ids
            - available_ids
        )

        if unknown_ids:
            raise ValueError(
                "指定的病例编号不存在："
                f"{unknown_ids}"
            )

        selected = [
            case
            for case in cases
            if str(
                case["case_id"]
            ).strip()
            in requested_ids
        ]

    if limit is not None:
        if limit <= 0:
            raise ValueError(
                "--limit 必须大于 0。"
            )

        selected = selected[
            :limit
        ]

    if not selected:
        raise ValueError(
            "筛选后没有可运行病例。"
        )

    return selected


def build_case_output_path(
    output_directory: Path,
    case_id: str,
) -> Path:
    """生成单病例稳定结果文件路径。"""

    safe_case_id = sanitize_filename(
        case_id
    )

    return (
        output_directory
        / f"comparison_{safe_case_id}.json"
    )


def read_case_status(
    result_file: Path,
) -> Dict[str, Any]:
    """读取已有单病例实验状态。"""

    if not result_file.exists():
        return {
            "exists": False,
            "success": False,
            "experiment_status": "",
            "fairness_passed": False,
            "error": "",
        }

    try:
        payload = load_json(
            result_file
        )

    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        return {
            "exists": True,
            "success": False,
            "experiment_status": "",
            "fairness_passed": False,
            "error": str(exc),
        }

    experiment_status = str(
        payload.get(
            "experiment_status",
            "",
        )
    )

    fairness = payload.get(
        "fairness_check",
        {},
    )

    fairness_passed = bool(
        fairness.get(
            "passed",
            False,
        )
        if isinstance(fairness, dict)
        else False
    )

    success = (
        experiment_status == "success"
        and fairness_passed
    )

    return {
        "exists": True,
        "success": success,
        "experiment_status": (
            experiment_status
        ),
        "fairness_passed": (
            fairness_passed
        ),
        "error": "",
    }


def build_command(
    case: Dict[str, Any],
    result_file: Path,
    top_k: int,
    max_hops: int,
    overwrite: bool,
) -> List[str]:
    """构造单病例三方法运行命令。"""

    command = [
        sys.executable,
        str(COMPARISON_RUNNER),
        "--case-id",
        str(case["case_id"]).strip(),
        "--disease",
        str(
            case["candidate_disease"]
        ).strip(),
        "--observation",
        str(
            case["user_observation"]
        ).strip(),
        "--top-k",
        str(top_k),
        "--max-hops",
        str(max_hops),
        "--output",
        str(result_file),
    ]

    if overwrite:
        command.append(
            "--overwrite"
        )

    return command


def run_case(
    case: Dict[str, Any],
    result_file: Path,
    top_k: int,
    max_hops: int,
    retry_count: int,
) -> Dict[str, Any]:
    """运行一个病例，失败时按配置进行重试。"""

    case_id = str(
        case["case_id"]
    ).strip()

    attempt_records: List[
        Dict[str, Any]
    ] = []

    total_attempts = (
        retry_count + 1
    )

    for attempt_index in range(
        1,
        total_attempts + 1,
    ):
        print("-" * 70)
        print(
            f"病例 {case_id}："
            f"第 {attempt_index}/{total_attempts} 次运行"
        )

        started_at = current_time()
        started_counter = (
            time.perf_counter()
        )

        overwrite = (
            result_file.exists()
        )

        command = build_command(
            case=case,
            result_file=result_file,
            top_k=top_k,
            max_hops=max_hops,
            overwrite=overwrite,
        )

        try:
            completed = subprocess.run(
                command,
                cwd=str(PROJECT_ROOT),
                check=False,
            )

            return_code = (
                completed.returncode
            )

            execution_error = ""

        except OSError as exc:
            return_code = -1
            execution_error = str(exc)

        elapsed_ms = int(
            round(
                (
                    time.perf_counter()
                    - started_counter
                )
                * 1000
            )
        )

        status = read_case_status(
            result_file
        )

        attempt_records.append(
            {
                "attempt": attempt_index,
                "started_at": started_at,
                "finished_at": current_time(),
                "elapsed_ms": elapsed_ms,
                "return_code": return_code,
                "execution_error": (
                    execution_error
                ),
                "result_status": status,
            }
        )

        if status["success"]:
            print(
                f"病例 {case_id} 运行成功。"
            )

            return {
                "case_id": case_id,
                "status": "success",
                "result_file": str(
                    result_file.relative_to(
                        PROJECT_ROOT
                    )
                ),
                "attempt_count": (
                    attempt_index
                ),
                "attempts": (
                    attempt_records
                ),
            }

        print(
            f"病例 {case_id} 本次运行未成功。"
        )
        print(
            "实验状态："
            f"{status['experiment_status'] or '未知'}"
        )
        print(
            "公平性检查："
            f"{status['fairness_passed']}"
        )

        if (
            attempt_index
            < total_attempts
        ):
            print(
                "准备重试该病例。"
            )

    return {
        "case_id": case_id,
        "status": "failed",
        "result_file": str(
            result_file.relative_to(
                PROJECT_ROOT
            )
        ),
        "attempt_count": (
            total_attempts
        ),
        "attempts": (
            attempt_records
        ),
    }


def calculate_summary(
    records: List[Dict[str, Any]],
) -> Dict[str, int]:
    """计算批量运行摘要。"""

    success_count = sum(
        1
        for record in records
        if record["status"] == "success"
    )

    skipped_count = sum(
        1
        for record in records
        if record["status"]
        == "skipped_existing_success"
    )

    failed_count = sum(
        1
        for record in records
        if record["status"] == "failed"
    )

    return {
        "selected_case_count": (
            len(records)
        ),
        "success_count": (
            success_count
        ),
        "skipped_count": (
            skipped_count
        ),
        "failed_count": (
            failed_count
        ),
        "completed_count": (
            success_count
            + skipped_count
        ),
    }


def print_plan(
    selected_cases: List[
        Dict[str, Any]
    ],
    output_directory: Path,
    top_k: int,
    max_hops: int,
    retry_count: int,
    resume: bool,
) -> None:
    """打印批量运行计划，不调用模型。"""

    print("=" * 70)
    print("任务四批量三方法实验计划")
    print("=" * 70)
    print(
        f"计划病例数量：{len(selected_cases)}"
    )
    print(
        f"单病例模型调用次数：3"
    )
    print(
        "预计模型调用总数："
        f"{len(selected_cases) * 3}"
    )
    print(f"统一 Top-k：{top_k}")
    print(
        f"KG-RAG 最大跳数：{max_hops}"
    )
    print(
        f"单病例失败重试次数：{retry_count}"
    )
    print(
        f"断点续跑：{'开启' if resume else '关闭'}"
    )
    print(
        f"结果目录：{output_directory}"
    )
    print("-" * 70)

    for case in selected_cases:
        case_id = str(
            case["case_id"]
        ).strip()

        disease = str(
            case["candidate_disease"]
        ).strip()

        result_file = (
            build_case_output_path(
                output_directory,
                case_id,
            )
        )

        existing_status = (
            read_case_status(
                result_file
            )
        )

        print(
            f"{case_id} | "
            f"{disease} | "
            f"已有成功结果="
            f"{existing_status['success']}"
        )

    print("-" * 70)
    print(
        "计划模式未调用大模型。"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "批量运行任务四的纯 LLM、"
            "普通 RAG 和 KG-RAG 对照实验。"
        )
    )

    parser.add_argument(
        "--case-file",
        type=Path,
        default=DEFAULT_CASE_FILE,
        help="固定病例集 JSON 文件",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIRECTORY,
        help="批量实验结果目录",
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help=(
            "普通 RAG 和 KG-RAG "
            "统一使用的 Top-k"
        ),
    )

    parser.add_argument(
        "--max-hops",
        type=int,
        choices=[1, 2],
        default=2,
        help="KG-RAG 最大路径跳数",
    )

    parser.add_argument(
        "--retry-count",
        type=int,
        default=1,
        help=(
            "单病例失败后的重试次数，"
            "默认 1"
        ),
    )

    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=2.0,
        help=(
            "相邻病例之间的等待秒数，"
            "默认 2"
        ),
    )

    parser.add_argument(
        "--case-id",
        action="append",
        default=None,
        help=(
            "只运行指定病例；"
            "可重复传入多个 --case-id"
        ),
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="只运行筛选结果中的前 N 个病例",
    )

    parser.add_argument(
        "--no-resume",
        action="store_true",
        help=(
            "关闭断点续跑，"
            "重新运行已有成功病例"
        ),
    )

    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="仅显示计划，不调用模型",
    )

    args = parser.parse_args()

    if args.top_k <= 0:
        parser.error(
            "--top-k 必须大于 0。"
        )

    if args.retry_count < 0:
        parser.error(
            "--retry-count 不能小于 0。"
        )

    if args.sleep_seconds < 0:
        parser.error(
            "--sleep-seconds 不能小于 0。"
        )

    case_file = args.case_file

    if not case_file.is_absolute():
        case_file = (
            PROJECT_ROOT
            / case_file
        )

    output_directory = (
        args.output_dir
    )

    if not output_directory.is_absolute():
        output_directory = (
            PROJECT_ROOT
            / output_directory
        )

    resume = not args.no_resume

    try:
        dataset = load_cases(
            case_file
        )

        selected_cases = select_cases(
            cases=dataset["cases"],
            selected_case_ids=(
                args.case_id
            ),
            limit=args.limit,
        )

    except (
        FileNotFoundError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        print(
            f"批量病例读取失败：{exc}"
        )
        return 1

    if args.plan_only:
        print_plan(
            selected_cases=selected_cases,
            output_directory=(
                output_directory
            ),
            top_k=args.top_k,
            max_hops=args.max_hops,
            retry_count=(
                args.retry_count
            ),
            resume=resume,
        )
        return 0

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    manifest_file = (
        output_directory
        / "batch_manifest.json"
    )

    batch_started_at = (
        current_time()
    )

    records: List[
        Dict[str, Any]
    ] = []

    manifest: Dict[str, Any] = {
        "batch_name": (
            "task4_three_method_batch_v1"
        ),
        "dataset_name": dataset.get(
            "dataset_name",
            "",
        ),
        "dataset_version": dataset.get(
            "dataset_version",
            "",
        ),
        "case_file": str(
            case_file.relative_to(
                PROJECT_ROOT
            )
        ),
        "started_at": batch_started_at,
        "updated_at": batch_started_at,
        "settings": {
            "top_k": args.top_k,
            "max_hops": args.max_hops,
            "retry_count": (
                args.retry_count
            ),
            "sleep_seconds": (
                args.sleep_seconds
            ),
            "resume": resume,
        },
        "case_results": records,
        "summary": {},
    }

    print("=" * 70)
    print("开始任务四批量三方法实验")
    print("=" * 70)
    print(
        f"本次选择病例数：{len(selected_cases)}"
    )
    print(
        "预计模型调用上限："
        f"{len(selected_cases) * 3}"
    )
    print(
        f"结果目录：{output_directory}"
    )

    for case_index, case in enumerate(
        selected_cases,
        start=1,
    ):
        case_id = str(
            case["case_id"]
        ).strip()

        disease = str(
            case["candidate_disease"]
        ).strip()

        result_file = (
            build_case_output_path(
                output_directory,
                case_id,
            )
        )

        print("=" * 70)
        print(
            f"[{case_index}/{len(selected_cases)}] "
            f"{case_id} | {disease}"
        )

        existing_status = (
            read_case_status(
                result_file
            )
        )

        if (
            resume
            and existing_status["success"]
        ):
            print(
                "已有成功结果，断点续跑模式下跳过。"
            )

            record = {
                "case_id": case_id,
                "status": (
                    "skipped_existing_success"
                ),
                "result_file": str(
                    result_file.relative_to(
                        PROJECT_ROOT
                    )
                ),
                "attempt_count": 0,
                "attempts": [],
            }

        else:
            record = run_case(
                case=case,
                result_file=result_file,
                top_k=args.top_k,
                max_hops=args.max_hops,
                retry_count=(
                    args.retry_count
                ),
            )

        records.append(
            record
        )

        manifest["updated_at"] = (
            current_time()
        )

        manifest["summary"] = (
            calculate_summary(
                records
            )
        )

        write_json(
            manifest,
            manifest_file,
        )

        if (
            case_index
            < len(selected_cases)
            and args.sleep_seconds > 0
        ):
            print(
                "等待 "
                f"{args.sleep_seconds} 秒后"
                "运行下一病例。"
            )

            time.sleep(
                args.sleep_seconds
            )

    summary = calculate_summary(
        records
    )

    manifest["finished_at"] = (
        current_time()
    )

    manifest["updated_at"] = (
        manifest["finished_at"]
    )

    manifest["summary"] = (
        summary
    )

    write_json(
        manifest,
        manifest_file,
    )

    print("=" * 70)
    print("任务四批量实验结束")
    print("=" * 70)
    print(
        "选择病例数："
        f"{summary['selected_case_count']}"
    )
    print(
        "本次成功数："
        f"{summary['success_count']}"
    )
    print(
        "跳过已有成功数："
        f"{summary['skipped_count']}"
    )
    print(
        "失败数："
        f"{summary['failed_count']}"
    )
    print(
        f"批量清单：{manifest_file}"
    )

    if summary["failed_count"] == 0:
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())