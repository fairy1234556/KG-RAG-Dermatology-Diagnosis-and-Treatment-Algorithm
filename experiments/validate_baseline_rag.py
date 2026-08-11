"""
Validate the ordinary RAG baseline without calling the real API.

Run:

    python experiments/validate_baseline_rag.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from rag.baseline_rag import RAGBaseline
from rag.baseline_rag import build_failed_result
from rag.llm_client import LLMResult
from rag.text_retriever import RetrievedDocument


class FakeTextRetriever:
    """模拟普通文本检索器，不读取知识图谱。"""

    def __init__(self) -> None:
        self.last_candidate_disease = ""
        self.last_user_observation = ""
        self.last_top_k = 0

    def retrieve(
        self,
        candidate_disease: str,
        user_observation: str,
        top_k: int = 5,
    ) -> List[RetrievedDocument]:
        self.last_candidate_disease = (
            candidate_disease
        )
        self.last_user_observation = (
            user_observation
        )
        self.last_top_k = top_k

        documents = [
            RetrievedDocument(
                rank=1,
                document_id="DOC_TEST_001",
                text=(
                    "结节型基底细胞癌可表现为"
                    "光亮或珍珠样结节。"
                ),
                score=8.5,
                bm25_score=8.15,
                phrase_overlap_score=0.35,
                matched_terms=(
                    "基底细胞癌",
                    "珍珠样结节",
                ),
                source_names=(
                    "DermNet - Basal Cell Carcinoma",
                ),
                origin_record_ids=(
                    "TRI_TEST_001",
                ),
            ),
            RetrievedDocument(
                rank=2,
                document_id="DOC_TEST_002",
                text=(
                    "基底细胞癌表面可见"
                    "毛细血管扩张。"
                ),
                score=7.9,
                bm25_score=7.55,
                phrase_overlap_score=0.35,
                matched_terms=(
                    "基底细胞癌",
                    "毛细血管",
                ),
                source_names=(
                    "DermNet - Basal Cell Carcinoma",
                ),
                origin_record_ids=(
                    "TRI_TEST_002",
                ),
            ),
            RetrievedDocument(
                rank=3,
                document_id="DOC_TEST_003",
                text=(
                    "结节型基底细胞癌是"
                    "面部常见的类型。"
                ),
                score=6.8,
                bm25_score=6.45,
                phrase_overlap_score=0.35,
                matched_terms=(
                    "基底细胞癌",
                    "面部",
                ),
                source_names=(
                    "DermNet - BCC Dermoscopy",
                ),
                origin_record_ids=(
                    "TRI_TEST_003",
                ),
            ),
        ]

        return documents[:top_k]


class FakeQwenClient:
    """模拟模型客户端，不产生网络请求。"""

    def __init__(self) -> None:
        self.last_user_prompt = ""
        self.last_system_prompt = ""
        self.last_json_mode = False

    def generate(
        self,
        user_prompt: str,
        system_prompt: Optional[str] = None,
        json_mode: bool = False,
    ) -> LLMResult:
        self.last_user_prompt = user_prompt
        self.last_system_prompt = (
            system_prompt or ""
        )
        self.last_json_mode = json_mode

        payload = {
            "observation_match": [
                "珍珠样结节与检索文本中的"
                "基底细胞癌表现相符。"
            ],
            "supporting_evidence": [
                "检索文本显示基底细胞癌可出现"
                "珍珠样结节和毛细血管扩张。"
            ],
            "differential_diagnosis": [],
            "risk_warning": [
                "仅凭外观不能确诊。"
            ],
            "medical_advice": [
                "建议由皮肤科医生进行评估。"
            ],
            "evidence_gap": [
                "缺少皮肤镜和病理检查结果。"
            ],
            # 故意返回不属于检索结果的来源，
            # 验证程序是否强制改成实际检索来源。
            "sources": [
                "模型虚构来源"
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
            request_id="fake-rag-request",
            prompt_tokens=300,
            completion_tokens=160,
            total_tokens=460,
            latency_seconds=0.75,
            temperature=0.1,
            max_completion_tokens=800,
            enable_thinking=False,
            seed=42,
        )


def print_separator() -> None:
    print("=" * 70)


def validate_success_result() -> bool:
    """验证普通 RAG 正常结果与实验边界。"""

    retriever = FakeTextRetriever()
    client = FakeQwenClient()

    baseline = RAGBaseline(
        retriever=retriever,
        client=client,
    )

    result = baseline.run(
        case_id="TEST_RAG_001",
        candidate_disease="基底细胞癌",
        user_observation=(
            "患者面部出现珍珠样结节，"
            "表面可见细小血管。"
        ),
        top_k=3,
    )

    errors: List[str] = []

    if result.case_id != "TEST_RAG_001":
        errors.append("case_id 不正确。")

    if result.method != "rag":
        errors.append("method 必须为 rag。")

    if result.run_status != "success":
        errors.append(
            "run_status 必须为 success。"
        )

    if result.model_name != (
        "qwen3.7-plus-2026-05-26"
    ):
        errors.append("模型名称记录不正确。")

    if result.evidence_paths:
        errors.append(
            "普通 RAG 的 evidence_paths 必须为空。"
        )

    expected_sources = [
        "DermNet - Basal Cell Carcinoma",
        "DermNet - BCC Dermoscopy",
    ]

    if result.sources != expected_sources:
        errors.append(
            "sources 没有被限制为实际检索来源："
            f"{result.sources}"
        )

    if "模型虚构来源" in result.sources:
        errors.append(
            "模型虚构的来源不应进入最终结果。"
        )

    if result.token_usage.prompt_tokens != 300:
        errors.append("输入 Token 记录不正确。")

    if result.token_usage.completion_tokens != 160:
        errors.append("输出 Token 记录不正确。")

    if result.token_usage.total_tokens != 460:
        errors.append("总 Token 记录不正确。")

    if result.response_time_ms != 750:
        errors.append("响应时间换算不正确。")

    if retriever.last_top_k != 3:
        errors.append(
            "top_k 未正确传递给检索器。"
        )

    if not client.last_json_mode:
        errors.append(
            "模型调用没有启用 JSON 模式。"
        )

    required_prompt_items = [
        "DOC_TEST_001",
        "DOC_TEST_002",
        "DOC_TEST_003",
        "珍珠样结节",
        "毛细血管扩张",
        "DermNet - Basal Cell Carcinoma",
    ]

    missing_prompt_items = [
        item
        for item in required_prompt_items
        if item not in client.last_user_prompt
    ]

    if missing_prompt_items:
        errors.append(
            "模型提示词缺少检索上下文："
            f"{missing_prompt_items}"
        )

    forbidden_graph_terms = [
        "relation_chain",
        "GraphPathRetriever",
        "SemanticAnchorMapper",
    ]

    present_graph_terms = [
        term
        for term in forbidden_graph_terms
        if term in client.last_user_prompt
    ]

    if present_graph_terms:
        errors.append(
            "普通 RAG 提示词中出现图谱模块信息："
            f"{present_graph_terms}"
        )

    print_separator()
    print(
        "RAG_VALIDATION_001："
        f"{'通过' if not errors else '失败'}"
    )
    print("测试名称：普通 RAG 正常结果与边界检查")
    print(f"method：{result.method}")
    print(f"run_status：{result.run_status}")
    print(f"sources：{result.sources}")
    print(
        f"evidence_paths：{result.evidence_paths}"
    )
    print(
        "total_tokens："
        f"{result.token_usage.total_tokens}"
    )

    for error in errors:
        print(f"错误：{error}")

    return not errors


def validate_top_k_context() -> bool:
    """验证不同 top_k 会限制发送给模型的文档数量。"""

    retriever = FakeTextRetriever()
    client = FakeQwenClient()

    baseline = RAGBaseline(
        retriever=retriever,
        client=client,
    )

    baseline.run(
        case_id="TEST_RAG_002",
        candidate_disease="基底细胞癌",
        user_observation="面部出现珍珠样结节。",
        top_k=2,
    )

    errors: List[str] = []

    if "DOC_TEST_001" not in client.last_user_prompt:
        errors.append(
            "Top-1 文档未进入模型提示词。"
        )

    if "DOC_TEST_002" not in client.last_user_prompt:
        errors.append(
            "Top-2 文档未进入模型提示词。"
        )

    if "DOC_TEST_003" in client.last_user_prompt:
        errors.append(
            "超过 top_k 的文档进入了模型提示词。"
        )

    print_separator()
    print(
        "RAG_VALIDATION_002："
        f"{'通过' if not errors else '失败'}"
    )
    print("测试名称：Top-k 上下文范围检查")
    print(f"传入 top_k：{retriever.last_top_k}")
    print(
        "包含 DOC_TEST_001："
        f"{'DOC_TEST_001' in client.last_user_prompt}"
    )
    print(
        "包含 DOC_TEST_002："
        f"{'DOC_TEST_002' in client.last_user_prompt}"
    )
    print(
        "包含 DOC_TEST_003："
        f"{'DOC_TEST_003' in client.last_user_prompt}"
    )

    for error in errors:
        print(f"错误：{error}")

    return not errors


def validate_input_constraints() -> bool:
    """验证必填输入和 top_k 参数。"""

    baseline = RAGBaseline(
        retriever=FakeTextRetriever(),
        client=FakeQwenClient(),
    )

    errors: List[str] = []

    invalid_cases = [
        {
            "case_id": "",
            "candidate_disease": "基底细胞癌",
            "user_observation": "面部出现结节。",
            "top_k": 5,
            "name": "空 case_id",
        },
        {
            "case_id": "TEST_RAG_003",
            "candidate_disease": "",
            "user_observation": "面部出现结节。",
            "top_k": 5,
            "name": "空 candidate_disease",
        },
        {
            "case_id": "TEST_RAG_004",
            "candidate_disease": "基底细胞癌",
            "user_observation": "",
            "top_k": 5,
            "name": "空 user_observation",
        },
        {
            "case_id": "TEST_RAG_005",
            "candidate_disease": "基底细胞癌",
            "user_observation": "面部出现结节。",
            "top_k": 0,
            "name": "非法 top_k",
        },
    ]

    for case in invalid_cases:
        try:
            baseline.run(
                case_id=case["case_id"],
                candidate_disease=case[
                    "candidate_disease"
                ],
                user_observation=case[
                    "user_observation"
                ],
                top_k=case["top_k"],
            )

            errors.append(
                f"{case['name']} 未触发 ValueError。"
            )

        except ValueError:
            pass

    print_separator()
    print(
        "RAG_VALIDATION_003："
        f"{'通过' if not errors else '失败'}"
    )
    print("测试名称：输入参数约束检查")

    for error in errors:
        print(f"错误：{error}")

    return not errors


def validate_failed_result() -> bool:
    """验证普通 RAG 失败结果结构。"""

    result = build_failed_result(
        case_id="TEST_RAG_006",
        candidate_disease="基底细胞癌",
        user_observation="面部出现结节。",
        error_message="模拟普通 RAG 失败",
    )

    errors: List[str] = []

    if result.method != "rag":
        errors.append(
            "失败结果 method 必须为 rag。"
        )

    if result.run_status != "failed":
        errors.append(
            "失败结果 run_status 必须为 failed。"
        )

    if result.error_message != (
        "模拟普通 RAG 失败"
    ):
        errors.append("错误信息记录不正确。")

    if result.sources:
        errors.append(
            "失败结果 sources 必须为空。"
        )

    if result.evidence_paths:
        errors.append(
            "失败结果 evidence_paths 必须为空。"
        )

    print_separator()
    print(
        "RAG_VALIDATION_004："
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
        validate_top_k_context(),
        validate_input_constraints(),
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
            "普通 RAG 基线验证通过："
            f"{total_count} 组检查全部通过。"
        )
        return 0

    print(
        "普通 RAG 基线验证未通过："
        f"{total_count - passed_count} 组检查失败。"
    )
    print(
        f"通过数量：{passed_count}/{total_count}"
    )

    return 1


if __name__ == "__main__":
    raise SystemExit(main())