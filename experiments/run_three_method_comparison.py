"""
Run the three-method dermatology explanation comparison.

Methods:

1. Pure LLM baseline.
2. Ordinary text RAG baseline.
3. Knowledge-graph-enhanced RAG.

All three methods share:

- the same candidate disease;
- the same user observation;
- the same Qwen client instance;
- the same model configuration;
- the same structured result schema.

Example:

    python experiments/run_three_method_comparison.py \
        --case-id CASE_001 \
        --disease "基底细胞癌" \
        --observation "患者面部出现光亮的珍珠样结节，表面可见细小血管。" \
        --top-k 5 \
        --max-hops 2
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from rag.baseline_common import result_to_dict
from rag.baseline_llm import LLMBaseline
from rag.baseline_llm import (
    build_failed_result as build_llm_failed_result,
)
from rag.baseline_rag import RAGBaseline
from rag.baseline_rag import (
    build_failed_result as build_rag_failed_result,
)
from rag.kg_rag_pipeline import KGRAGPipeline
from rag.kg_rag_pipeline import (
    build_failed_result as build_kg_rag_failed_result,
)
from rag.llm_client import QwenLLMClient
from rag.schemas import KGRAGResult


DEFAULT_RESULT_DIRECTORY = (
    PROJECT_ROOT
    / "experiments"
    / "results"
)

LLM_CONFIG_FILE = (
    PROJECT_ROOT
    / "configs"
    / "llm_config.yaml"
)

METHOD_ORDER = [
    "llm",
    "rag",
    "kg_rag",
]


def sanitize_filename(value: str) -> str:
    """将病例编号转换为安全文件名。"""

    cleaned = re.sub(
        r"[^A-Za-z0-9._-]+",
        "_",
        (value or "").strip(),
    )

    cleaned = cleaned.strip(
        "._-"
    )

    return cleaned or "case"


def calculate_file_sha256(
    file_path: Path,
) -> str:
    """计算配置文件的 SHA256，用于实验复现。"""

    if not file_path.exists():
        return ""

    digest = hashlib.sha256()

    with file_path.open("rb") as file:
        while True:
            chunk = file.read(
                8192
            )

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()


def run_git_command(
    arguments: List[str],
) -> str:
    """安全读取当前 Git 元数据。"""

    try:
        completed = subprocess.run(
            ["git"] + arguments,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )

    except OSError:
        return ""

    if completed.returncode != 0:
        return ""

    return completed.stdout.strip()


def collect_git_metadata() -> Dict[str, Any]:
    """记录当前代码版本，保证实验可追溯。"""

    commit = run_git_command(
        [
            "rev-parse",
            "HEAD",
        ]
    )

    branch = run_git_command(
        [
            "rev-parse",
            "--abbrev-ref",
            "HEAD",
        ]
    )

    status = run_git_command(
        [
            "status",
            "--short",
        ]
    )

    return {
        "branch": branch,
        "commit": commit,
        "working_tree_dirty": bool(status),
        "working_tree_status": (
            status.splitlines()
            if status
            else []
        ),
    }


def build_default_output_path(
    case_id: str,
) -> Path:
    """生成不覆盖历史结果的默认输出路径。"""

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    safe_case_id = sanitize_filename(
        case_id
    )

    filename = (
        f"task4_comparison_"
        f"{safe_case_id}_"
        f"{timestamp}.json"
    )

    return (
        DEFAULT_RESULT_DIRECTORY
        / filename
    )


def write_json_result(
    payload: Dict[str, Any],
    output_file: Path,
    overwrite: bool = False,
) -> None:
    """将统一实验结果写入 JSON 文件。"""

    if output_file.exists() and not overwrite:
        raise FileExistsError(
            "输出文件已经存在。"
            "如需覆盖，请增加 --overwrite："
            f"{output_file}"
        )

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_file.open(
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


def run_single_method(
    method_name: str,
    runner: Callable[
        [],
        KGRAGResult,
    ],
    failed_result_builder: Callable[
        ...,
        KGRAGResult,
    ],
    case_id: str,
    candidate_disease: str,
    user_observation: str,
) -> Tuple[
    KGRAGResult,
    Dict[str, Any],
]:
    """
    运行单个实验方法。

    某一种方法失败时，不中断其他方法，
    而是保存统一失败结果。
    """

    started_at = (
        datetime.now()
        .astimezone()
        .isoformat(
            timespec="seconds"
        )
    )

    started_counter = (
        time.perf_counter()
    )

    try:
        result = runner()

    except Exception as exc:
        error_message = (
            f"{type(exc).__name__}: {exc}"
        )

        result = failed_result_builder(
            case_id=case_id,
            candidate_disease=(
                candidate_disease
            ),
            user_observation=(
                user_observation
            ),
            error_message=error_message,
        )

    wall_time_ms = int(
        round(
            (
                time.perf_counter()
                - started_counter
            )
            * 1000
        )
    )

    record = {
        "method": method_name,
        "started_at": started_at,
        "wall_time_ms": wall_time_ms,
        "result": result_to_dict(
            result
        ),
    }

    return result, record


def evaluate_fairness(
    results: List[KGRAGResult],
) -> Dict[str, Any]:
    """检查三种实验方法是否满足基本公平性要求。"""

    successful_results = [
        result
        for result in results
        if result.run_status
        == "success"
    ]

    method_names = [
        result.method
        for result in results
    ]

    model_names = unique_non_empty(
        [
            result.model_name
            for result
            in successful_results
        ]
    )

    prompt_versions = unique_non_empty(
        [
            result.prompt_version
            for result
            in successful_results
        ]
    )

    same_case_input = all(
        result.case_id
        == results[0].case_id
        and result.candidate_disease
        == results[0].candidate_disease
        and result.user_observation
        == results[0].user_observation
        for result in results
    )

    method_mapping_correct = (
        method_names
        == METHOD_ORDER
    )

    checks = {
        "all_use_unified_schema": all(
            isinstance(
                result,
                KGRAGResult,
            )
            for result in results
        ),
        "same_case_input": (
            same_case_input
        ),
        "method_order_correct": (
            method_mapping_correct
        ),
        "same_model_for_successful_runs": (
            len(model_names) <= 1
        ),
        "same_prompt_version_for_successful_runs": (
            len(prompt_versions) <= 1
        ),
        "shared_client_instance": True,
    }

    return {
        "passed": all(
            checks.values()
        ),
        "checks": checks,
        "successful_model_names": (
            model_names
        ),
        "successful_prompt_versions": (
            prompt_versions
        ),
    }


def unique_non_empty(
    values: List[str],
) -> List[str]:
    """保留顺序，去除空值与重复值。"""

    result: List[str] = []

    for value in values:
        cleaned = (
            value or ""
        ).strip()

        if (
            cleaned
            and cleaned not in result
        ):
            result.append(cleaned)

    return result


def print_plan(
    case_id: str,
    disease: str,
    observation: str,
    top_k: int,
    max_hops: int,
    output_file: Path,
) -> None:
    """打印实验计划，不调用模型。"""

    print("=" * 70)
    print("三方法对照实验计划")
    print("=" * 70)
    print(f"病例编号：{case_id}")
    print(f"候选疾病：{disease}")
    print(f"用户观察：{observation}")
    print(f"方法顺序：{' → '.join(METHOD_ORDER)}")
    print(f"普通 RAG Top-k：{top_k}")
    print(f"KG-RAG Top-k：{top_k}")
    print(f"KG-RAG 最大跳数：{max_hops}")
    print(f"统一模型配置：{LLM_CONFIG_FILE}")
    print(f"计划输出文件：{output_file}")
    print("计划模式未调用大模型。")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "运行纯 LLM、普通 RAG 和 KG-RAG "
            "三种方法的统一对照实验。"
        )
    )

    parser.add_argument(
        "--case-id",
        required=True,
        help="实验病例编号",
    )

    parser.add_argument(
        "--disease",
        required=True,
        help="候选疾病名称",
    )

    parser.add_argument(
        "--observation",
        required=True,
        help="用户观察文本",
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help=(
            "普通 RAG 和 KG-RAG "
            "统一使用的 Top-k，默认 5"
        ),
    )

    parser.add_argument(
        "--max-hops",
        type=int,
        choices=[1, 2],
        default=2,
        help=(
            "KG-RAG 最大图谱跳数，默认 2"
        ),
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="指定实验结果 JSON 文件",
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="允许覆盖已经存在的结果文件",
    )

    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="仅显示实验计划，不调用模型",
    )

    args = parser.parse_args()

    case_id = (
        args.case_id or ""
    ).strip()

    candidate_disease = (
        args.disease or ""
    ).strip()

    user_observation = (
        args.observation or ""
    ).strip()

    if not case_id:
        parser.error(
            "--case-id 不能为空。"
        )

    if not candidate_disease:
        parser.error(
            "--disease 不能为空。"
        )

    if not user_observation:
        parser.error(
            "--observation 不能为空。"
        )

    if args.top_k <= 0:
        parser.error(
            "--top-k 必须大于 0。"
        )

    output_file = (
        args.output
        if args.output is not None
        else build_default_output_path(
            case_id
        )
    )

    if not output_file.is_absolute():
        output_file = (
            PROJECT_ROOT
            / output_file
        )

    if args.plan_only:
        print_plan(
            case_id=case_id,
            disease=candidate_disease,
            observation=user_observation,
            top_k=args.top_k,
            max_hops=args.max_hops,
            output_file=output_file,
        )
        return 0

    experiment_started_at = (
        datetime.now()
        .astimezone()
        .isoformat(
            timespec="seconds"
        )
    )

    experiment_start_counter = (
        time.perf_counter()
    )

    # 三种方法共享同一个模型客户端，
    # 以保证模型和生成参数一致。
    shared_client = QwenLLMClient()

    llm_baseline = LLMBaseline(
        client=shared_client
    )

    rag_baseline = RAGBaseline(
        client=shared_client
    )

    kg_rag_pipeline = KGRAGPipeline(
        client=shared_client
    )

    method_specs = [
        (
            "llm",
            lambda: llm_baseline.run(
                case_id=case_id,
                candidate_disease=(
                    candidate_disease
                ),
                user_observation=(
                    user_observation
                ),
            ),
            build_llm_failed_result,
        ),
        (
            "rag",
            lambda: rag_baseline.run(
                case_id=case_id,
                candidate_disease=(
                    candidate_disease
                ),
                user_observation=(
                    user_observation
                ),
                top_k=args.top_k,
            ),
            build_rag_failed_result,
        ),
        (
            "kg_rag",
            lambda: kg_rag_pipeline.run(
                case_id=case_id,
                candidate_disease=(
                    candidate_disease
                ),
                user_observation=(
                    user_observation
                ),
                top_k=args.top_k,
                max_hops=args.max_hops,
            ),
            build_kg_rag_failed_result,
        ),
    ]

    results: List[
        KGRAGResult
    ] = []

    method_records: List[
        Dict[str, Any]
    ] = []

    for (
        method_name,
        runner,
        failure_builder,
    ) in method_specs:
        print(
            f"正在运行：{method_name}"
        )

        result, record = (
            run_single_method(
                method_name=method_name,
                runner=runner,
                failed_result_builder=(
                    failure_builder
                ),
                case_id=case_id,
                candidate_disease=(
                    candidate_disease
                ),
                user_observation=(
                    user_observation
                ),
            )
        )

        results.append(result)
        method_records.append(record)

        print(
            f"完成：{method_name} | "
            f"状态={result.run_status} | "
            f"耗时={record['wall_time_ms']} ms | "
            f"Token={result.token_usage.total_tokens}"
        )

    total_wall_time_ms = int(
        round(
            (
                time.perf_counter()
                - experiment_start_counter
            )
            * 1000
        )
    )

    success_count = sum(
        1
        for result in results
        if result.run_status
        == "success"
    )

    if success_count == len(results):
        experiment_status = "success"

    elif success_count == 0:
        experiment_status = "failed"

    else:
        experiment_status = (
            "partial_failure"
        )

    fairness = evaluate_fairness(
        results
    )

    experiment_payload = {
        "experiment_id": (
            f"TASK4_{sanitize_filename(case_id)}_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        ),
        "task": (
            "three_method_baseline_comparison"
        ),
        "experiment_status": (
            experiment_status
        ),
        "started_at": (
            experiment_started_at
        ),
        "finished_at": (
            datetime.now()
            .astimezone()
            .isoformat(
                timespec="seconds"
            )
        ),
        "total_wall_time_ms": (
            total_wall_time_ms
        ),
        "case": {
            "case_id": case_id,
            "candidate_disease": (
                candidate_disease
            ),
            "user_observation": (
                user_observation
            ),
        },
        "experiment_settings": {
            "method_order": METHOD_ORDER,
            "rag_top_k": args.top_k,
            "kg_rag_top_k": args.top_k,
            "kg_rag_max_hops": (
                args.max_hops
            ),
            "shared_llm_client": True,
            "llm_config_path": str(
                LLM_CONFIG_FILE.relative_to(
                    PROJECT_ROOT
                )
            ),
            "llm_config_sha256": (
                calculate_file_sha256(
                    LLM_CONFIG_FILE
                )
            ),
        },
        "git": collect_git_metadata(),
        "fairness_check": fairness,
        "method_results": (
            method_records
        ),
        "summary": {
            "method_count": len(results),
            "success_count": (
                success_count
            ),
            "failed_count": (
                len(results)
                - success_count
            ),
            "total_tokens": sum(
                result.token_usage.total_tokens
                for result in results
            ),
        },
    }

    try:
        write_json_result(
            payload=experiment_payload,
            output_file=output_file,
            overwrite=args.overwrite,
        )

    except (
        FileExistsError,
        OSError,
    ) as exc:
        print(
            f"实验结果写入失败：{exc}"
        )
        return 1

    print("=" * 70)
    print("三方法对照实验运行完成")
    print(f"实验状态：{experiment_status}")
    print(
        "公平性检查："
        f"{'通过' if fairness['passed'] else '未通过'}"
    )
    print(
        f"成功方法数：{success_count}/"
        f"{len(results)}"
    )
    print(
        "总 Token："
        f"{experiment_payload['summary']['total_tokens']}"
    )
    print(
        f"总耗时：{total_wall_time_ms} ms"
    )
    print(
        f"结果文件：{output_file}"
    )

    if (
        experiment_status == "success"
        and fairness["passed"]
    ):
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())