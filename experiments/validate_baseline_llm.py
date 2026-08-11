"""
Validate the pure LLM baseline without calling the real API.

Run:

    python experiments/validate_baseline_llm.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from rag.baseline_llm import LLMBaseline
from rag.baseline_llm import build_failed_result
from rag.llm_client import LLMResult


class FakeQwenClient:
    """用于自动测试的模拟模型客户端，不产生网络请求。"""

    def generate(
        self,
        user_prompt: str,
        system_prompt: str = None,
        json_mode: bool = False,
    ) -> LLMResult:
        payload = {
            "observation_match": [
                "珍珠样结节与候选疾病的一般表现存在对应关系。"
            ],
            "supporting_evidence": [
                "基底细胞癌可出现珍珠样结节。"
            ],
            "differential_diagnosis": [
                "需要与其他面部丘疹或结节性病变鉴别。"
            ],
            "risk_warning": [
                "仅凭外观不能确诊。"
            ],
            "medical_advice": [
                "建议前往皮肤科进行专业评估。"
            ],
            "evidence_gap": [
                "缺少皮肤镜和组织病理检查结果。"
            ],
            # 故意返回伪来源，验证纯 LLM 边界是否强制清空。
            "sources": [
                "不应保留的模拟来源"
            ],
        }

        return LLMResult(
            content=json.dumps(
                payload,
                ensure_ascii=False,
            ),
            model="qwen3.7-plus-2026-05-26",
            provider="aliyun_bailian",
            prompt_version="baseline_v1",
            finish_reason="stop",
            request_id="fake-request-id",
            prompt_tokens=100,
            completion_tokens=80,
            total_tokens=180,
            latency_seconds=0.25,
            temperature=0.1,
            max_completion_tokens=800,
            enable_thinking=False,
            seed=42,
        )


def print_separator() -> None:
    print("=" * 70)


def validate_success_result() -> bool:
    """验证正常运行结果及纯 LLM 实验边界。"""

    baseline = LLMBaseline(
        client=FakeQwenClient()
    )

    result = baseline.run(
        case_id="TEST_LLM_001",
        candidate_disease="基底细胞癌",
        user_observation=(
            "患者面部出现珍珠样结节，"
            "表面可见细小血管。"
        ),
    )

    errors = []

    if result.case_id != "TEST_LLM_001":
        errors.append("case_id 不正确。")

    if result.method != "llm":
        errors.append("method 必须为 llm。")

    if result.run_status != "success":
        errors.append("run_status 必须为 success。")

    if result.model_name != (
        "qwen3.7-plus-2026-05-26"
    ):
        errors.append("模型名称记录不正确。")

    if result.prompt_version != "baseline_v1":
        errors.append("提示词版本记录不正确。")

    if result.token_usage.prompt_tokens != 100:
        errors.append("输入 Token 记录不正确。")

    if result.token_usage.completion_tokens != 80:
        errors.append("输出 Token 记录不正确。")

    if result.token_usage.total_tokens != 180:
        errors.append("总 Token 记录不正确。")

    if result.response_time_ms != 250:
        errors.append("响应时间换算不正确。")

    if result.evidence_paths:
        errors.append(
            "纯 LLM 的 evidence_paths 必须为空。"
        )

    if result.sources:
        errors.append(
            "纯 LLM 的 sources 必须被强制清空。"
        )

    boundary_message = (
        "纯 LLM 基线未接入外部检索证据，"
        "回答中的医学内容不具备本次运行级别的来源追溯能力。"
    )

    if boundary_message not in result.evidence_gap:
        errors.append(
            "缺少纯 LLM 来源不可追溯说明。"
        )

    if not result.supporting_evidence:
        errors.append("支持证据字段不应为空。")

    print_separator()
    print(
        "LLM_VALIDATION_001："
        f"{'通过' if not errors else '失败'}"
    )
    print("测试名称：纯 LLM 正常结果与边界检查")
    print(f"method：{result.method}")
    print(f"run_status：{result.run_status}")
    print(f"model_name：{result.model_name}")
    print(
        "total_tokens："
        f"{result.token_usage.total_tokens}"
    )
    print(
        "evidence_paths："
        f"{result.evidence_paths}"
    )
    print(f"sources：{result.sources}")

    for error in errors:
        print(f"错误：{error}")

    return not errors


def validate_input_check() -> bool:
    """验证空输入会被拒绝。"""

    baseline = LLMBaseline(
        client=FakeQwenClient()
    )

    errors = []

    try:
        baseline.run(
            case_id="",
            candidate_disease="基底细胞癌",
            user_observation="面部出现结节。",
        )

        errors.append(
            "空 case_id 未触发 ValueError。"
        )

    except ValueError:
        pass

    try:
        baseline.run(
            case_id="TEST_LLM_002",
            candidate_disease="",
            user_observation="面部出现结节。",
        )

        errors.append(
            "空 candidate_disease 未触发 ValueError。"
        )

    except ValueError:
        pass

    try:
        baseline.run(
            case_id="TEST_LLM_003",
            candidate_disease="基底细胞癌",
            user_observation="",
        )

        errors.append(
            "空 user_observation 未触发 ValueError。"
        )

    except ValueError:
        pass

    print_separator()
    print(
        "LLM_VALIDATION_002："
        f"{'通过' if not errors else '失败'}"
    )
    print("测试名称：必填输入检查")

    for error in errors:
        print(f"错误：{error}")

    return not errors


def validate_failed_result() -> bool:
    """验证失败结果符合统一结构。"""

    result = build_failed_result(
        case_id="TEST_LLM_004",
        candidate_disease="基底细胞癌",
        user_observation="面部出现结节。",
        error_message="模拟模型调用失败",
    )

    errors = []

    if result.method != "llm":
        errors.append("失败结果 method 不正确。")

    if result.run_status != "failed":
        errors.append(
            "失败结果 run_status 必须为 failed。"
        )

    if result.error_message != "模拟模型调用失败":
        errors.append("错误信息记录不正确。")

    if result.sources:
        errors.append(
            "失败结果的 sources 必须为空。"
        )

    if result.evidence_paths:
        errors.append(
            "失败结果的 evidence_paths 必须为空。"
        )

    print_separator()
    print(
        "LLM_VALIDATION_003："
        f"{'通过' if not errors else '失败'}"
    )
    print("测试名称：统一失败结果检查")
    print(f"run_status：{result.run_status}")
    print(f"error_message：{result.error_message}")

    for error in errors:
        print(f"错误：{error}")

    return not errors


def main() -> int:
    results = [
        validate_success_result(),
        validate_input_check(),
        validate_failed_result(),
    ]

    print_separator()

    passed_count = sum(
        1
        for passed in results
        if passed
    )

    total_count = len(results)

    if passed_count == total_count:
        print(
            "纯 LLM 基线验证通过："
            f"{total_count} 组检查全部通过。"
        )
        return 0

    print(
        "纯 LLM 基线验证未通过："
        f"{total_count - passed_count} 组检查失败。"
    )
    print(
        f"通过数量：{passed_count}/{total_count}"
    )

    return 1


if __name__ == "__main__":
    raise SystemExit(main())