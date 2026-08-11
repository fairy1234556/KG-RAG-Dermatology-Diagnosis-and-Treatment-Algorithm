"""
Validate the KG-RAG pipeline without calling the real API.

Run:

    python experiments/validate_kg_rag_pipeline.py
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from rag.kg_rag_pipeline import KGRAGPipeline
from rag.kg_rag_pipeline import build_failed_result
from rag.llm_client import LLMResult


@dataclass(frozen=True)
class FakeAnchor:
    """模拟语义锚点。"""

    matched_text: str
    entity_name: str
    entity_id: str
    confidence: float


@dataclass(frozen=True)
class FakeEdge:
    """模拟知识图谱路径中的一条边。"""

    head_name: str
    relation_cn: str
    tail_name: str
    evidence_text: str
    triple_id: str


@dataclass(frozen=True)
class FakeGraphPath:
    """模拟一跳或二跳知识图谱路径。"""

    edges: Tuple[FakeEdge, ...]


@dataclass(frozen=True)
class FakeRankedPath:
    """模拟任务三输出的排序证据链。"""

    rank: int
    path_id: str
    path: FakeGraphPath
    hop_count: int
    start_disease_name: str
    end_entity_id: str
    end_entity_name: str
    matched_anchor_names: Tuple[str, ...]
    evidence_texts: Tuple[str, ...]
    source_names: Tuple[str, ...]
    total_score: float
    entity_match_score: float
    relation_weight_score: float
    disease_match_score: float
    path_length_penalty: float


def build_fake_paths() -> List[FakeRankedPath]:
    """构造一跳和二跳模拟证据链。"""

    pearl_path = FakeRankedPath(
        rank=1,
        path_id="PATH_TEST_001",
        path=FakeGraphPath(
            edges=(
                FakeEdge(
                    head_name="基底细胞癌",
                    relation_cn="表现为",
                    tail_name="珍珠样结节",
                    evidence_text=(
                        "结节型基底细胞癌可表现为"
                        "光亮或珍珠样结节。"
                    ),
                    triple_id="TRI_TEST_001",
                ),
            )
        ),
        hop_count=1,
        start_disease_name="基底细胞癌",
        end_entity_id="SYM_TEST_001",
        end_entity_name="珍珠样结节",
        matched_anchor_names=(
            "珍珠样结节",
        ),
        evidence_texts=(
            "结节型基底细胞癌可表现为"
            "光亮或珍珠样结节。",
        ),
        source_names=(
            "DermNet - Basal Cell Carcinoma",
        ),
        total_score=4.42,
        entity_match_score=2.0,
        relation_weight_score=1.42,
        disease_match_score=1.0,
        path_length_penalty=0.0,
    )

    vessel_path = FakeRankedPath(
        rank=2,
        path_id="PATH_TEST_002",
        path=FakeGraphPath(
            edges=(
                FakeEdge(
                    head_name="基底细胞癌",
                    relation_cn="表现为",
                    tail_name="表面毛细血管扩张",
                    evidence_text=(
                        "基底细胞癌表面可见"
                        "血管穿过。"
                    ),
                    triple_id="TRI_TEST_002",
                ),
            )
        ),
        hop_count=1,
        start_disease_name="基底细胞癌",
        end_entity_id="SYM_TEST_002",
        end_entity_name="表面毛细血管扩张",
        matched_anchor_names=(
            "表面毛细血管扩张",
        ),
        evidence_texts=(
            "基底细胞癌表面可见血管穿过。",
        ),
        source_names=(
            "DermNet - Basal Cell Carcinoma",
        ),
        total_score=4.34,
        entity_match_score=2.0,
        relation_weight_score=1.34,
        disease_match_score=1.0,
        path_length_penalty=0.0,
    )

    differential_path = FakeRankedPath(
        rank=3,
        path_id="PATH_TEST_003",
        path=FakeGraphPath(
            edges=(
                FakeEdge(
                    head_name="基底细胞癌",
                    relation_cn="鉴别诊断",
                    tail_name="皮脂腺增生",
                    evidence_text=(
                        "皮脂腺增生需要与"
                        "基底细胞癌进行鉴别。"
                    ),
                    triple_id="TRI_TEST_003",
                ),
                FakeEdge(
                    head_name="皮脂腺增生",
                    relation_cn="表现为",
                    tail_name="黄色丘疹",
                    evidence_text=(
                        "皮脂腺增生可表现为"
                        "黄色或肤色丘疹。"
                    ),
                    triple_id="TRI_TEST_004",
                ),
            )
        ),
        hop_count=2,
        start_disease_name="基底细胞癌",
        end_entity_id="SYM_TEST_003",
        end_entity_name="黄色丘疹",
        matched_anchor_names=(),
        evidence_texts=(
            "皮脂腺增生需要与基底细胞癌进行鉴别。",
            "皮脂腺增生可表现为黄色或肤色丘疹。",
        ),
        source_names=(
            "DermNet - Sebaceous Hyperplasia",
        ),
        total_score=2.75,
        entity_match_score=0.0,
        relation_weight_score=1.25,
        disease_match_score=1.0,
        path_length_penalty=-0.5,
    )

    return [
        pearl_path,
        vessel_path,
        differential_path,
    ]


class FakeEvidencePathRanker:
    """模拟路径排序器，不读取真实知识图谱文件。"""

    def __init__(
        self,
        return_anchors: bool = True,
    ) -> None:
        self.return_anchors = return_anchors
        self.last_disease_query = ""
        self.last_observation_text = ""
        self.last_top_k = 0
        self.last_max_hops = 0

    def rank(
        self,
        disease_query: str,
        observation_text: str,
        top_k: int = 5,
        max_hops: int = 2,
    ):
        self.last_disease_query = (
            disease_query
        )
        self.last_observation_text = (
            observation_text
        )
        self.last_top_k = top_k
        self.last_max_hops = max_hops

        anchors = []

        if self.return_anchors:
            anchors = [
                FakeAnchor(
                    matched_text="珍珠样结节",
                    entity_name="珍珠样结节",
                    entity_id="SYM_TEST_001",
                    confidence=1.0,
                ),
                FakeAnchor(
                    matched_text="细小血管",
                    entity_name="表面毛细血管扩张",
                    entity_id="SYM_TEST_002",
                    confidence=0.95,
                ),
            ]

        paths = build_fake_paths()

        return (
            anchors,
            paths[:top_k],
            len(paths),
        )


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
                "珍珠样结节与图谱证据直接匹配。",
                "细小血管与表面毛细血管扩张匹配。",
            ],
            "supporting_evidence": [
                "图谱证据显示基底细胞癌"
                "可表现为珍珠样结节。",
            ],
            "differential_diagnosis": [
                "需要与皮脂腺增生鉴别。"
            ],
            "risk_warning": [
                "仅凭皮损外观不能确诊。"
            ],
            "medical_advice": [
                "建议前往皮肤科进行评估。"
            ],
            "evidence_gap": [
                "缺少皮肤镜和病理检查结果。"
            ],
            # 故意返回虚构来源，验证最终结果是否覆盖。
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
            request_id="fake-kg-rag-request",
            prompt_tokens=500,
            completion_tokens=220,
            total_tokens=720,
            latency_seconds=1.25,
            temperature=0.1,
            max_completion_tokens=800,
            enable_thinking=False,
            seed=42,
        )


def print_separator() -> None:
    print("=" * 70)


def validate_success_result() -> bool:
    """验证 KG-RAG 正常结果和来源边界。"""

    ranker = FakeEvidencePathRanker()
    client = FakeQwenClient()

    pipeline = KGRAGPipeline(
        ranker=ranker,
        client=client,
    )

    result = pipeline.run(
        case_id="TEST_KG_RAG_001",
        candidate_disease="基底细胞癌",
        user_observation=(
            "患者面部出现珍珠样结节，"
            "表面可见细小血管。"
        ),
        top_k=3,
        max_hops=2,
    )

    errors: List[str] = []

    if result.case_id != "TEST_KG_RAG_001":
        errors.append("case_id 不正确。")

    if result.method != "kg_rag":
        errors.append(
            "method 必须为 kg_rag。"
        )

    if result.run_status != "success":
        errors.append(
            "run_status 必须为 success。"
        )

    if result.model_name != (
        "qwen3.7-plus-2026-05-26"
    ):
        errors.append(
            "模型名称记录不正确。"
        )

    if len(result.evidence_paths) != 3:
        errors.append(
            "evidence_paths 数量不正确："
            f"{len(result.evidence_paths)}"
        )

    expected_sources = [
        "DermNet - Basal Cell Carcinoma",
        "DermNet - Sebaceous Hyperplasia",
    ]

    if result.sources != expected_sources:
        errors.append(
            "sources 没有被限制为实际图谱来源："
            f"{result.sources}"
        )

    if "模型虚构来源" in result.sources:
        errors.append(
            "模型虚构来源进入了最终结果。"
        )

    if result.token_usage.total_tokens != 720:
        errors.append(
            "Token 使用量记录不正确。"
        )

    if result.response_time_ms != 1250:
        errors.append(
            "响应时间换算不正确。"
        )

    if ranker.last_top_k != 3:
        errors.append(
            "top_k 未正确传递给路径排序器。"
        )

    if ranker.last_max_hops != 2:
        errors.append(
            "max_hops 未正确传递给路径排序器。"
        )

    if not client.last_json_mode:
        errors.append(
            "模型调用未启用 JSON 模式。"
        )

    if result.evidence_paths:
        first_path = result.evidence_paths[0]

        if first_path.head_entity != "基底细胞癌":
            errors.append(
                "第一条路径头实体不正确。"
            )

        if first_path.relation != "表现为":
            errors.append(
                "第一条路径关系不正确。"
            )

        if first_path.tail_entity != "珍珠样结节":
            errors.append(
                "第一条路径尾实体不正确。"
            )

        if first_path.source_id != "TRI_TEST_001":
            errors.append(
                "第一条路径来源编号不正确。"
            )

        if first_path.score != 4.42:
            errors.append(
                "第一条路径得分不正确。"
            )

    if len(result.evidence_paths) >= 3:
        third_path = result.evidence_paths[2]

        expected_relation = (
            "鉴别诊断 → 表现为"
        )

        if third_path.relation != expected_relation:
            errors.append(
                "二跳路径关系链不正确："
                f"{third_path.relation}"
            )

        expected_source_id = (
            "TRI_TEST_003；TRI_TEST_004"
        )

        if third_path.source_id != expected_source_id:
            errors.append(
                "二跳路径来源编号合并不正确："
                f"{third_path.source_id}"
            )

    required_prompt_items = [
        "珍珠样结节 → 珍珠样结节",
        "细小血管 → 表面毛细血管扩张",
        "PATH_TEST_001",
        "PATH_TEST_002",
        "PATH_TEST_003",
        "基底细胞癌 → 鉴别诊断 → 皮脂腺增生",
        "皮脂腺增生 → 表现为 → 黄色丘疹",
    ]

    missing_prompt_items = [
        item
        for item in required_prompt_items
        if item not in client.last_user_prompt
    ]

    if missing_prompt_items:
        errors.append(
            "模型提示词缺少语义锚点或图谱路径："
            f"{missing_prompt_items}"
        )

    print_separator()
    print(
        "KG_RAG_VALIDATION_001："
        f"{'通过' if not errors else '失败'}"
    )
    print("测试名称：正常结果与图谱边界检查")
    print(f"method：{result.method}")
    print(f"run_status：{result.run_status}")
    print(
        "evidence_paths 数量："
        f"{len(result.evidence_paths)}"
    )
    print(f"sources：{result.sources}")
    print(
        "total_tokens："
        f"{result.token_usage.total_tokens}"
    )

    for error in errors:
        print(f"错误：{error}")

    return not errors


def validate_top_k_context() -> bool:
    """验证 Top-k 限制发送给模型的路径数量。"""

    ranker = FakeEvidencePathRanker()
    client = FakeQwenClient()

    pipeline = KGRAGPipeline(
        ranker=ranker,
        client=client,
    )

    result = pipeline.run(
        case_id="TEST_KG_RAG_002",
        candidate_disease="基底细胞癌",
        user_observation="面部出现珍珠样结节。",
        top_k=2,
        max_hops=2,
    )

    errors: List[str] = []

    if len(result.evidence_paths) != 2:
        errors.append(
            "Top-k=2 时 evidence_paths "
            f"数量实际为 {len(result.evidence_paths)}。"
        )

    if "PATH_TEST_001" not in client.last_user_prompt:
        errors.append(
            "Top-1 路径未进入模型提示词。"
        )

    if "PATH_TEST_002" not in client.last_user_prompt:
        errors.append(
            "Top-2 路径未进入模型提示词。"
        )

    if "PATH_TEST_003" in client.last_user_prompt:
        errors.append(
            "超过 Top-k 的路径进入模型提示词。"
        )

    print_separator()
    print(
        "KG_RAG_VALIDATION_002："
        f"{'通过' if not errors else '失败'}"
    )
    print("测试名称：Top-k 图谱上下文范围检查")
    print(
        f"返回路径数量：{len(result.evidence_paths)}"
    )
    print(
        "包含 PATH_TEST_001："
        f"{'PATH_TEST_001' in client.last_user_prompt}"
    )
    print(
        "包含 PATH_TEST_002："
        f"{'PATH_TEST_002' in client.last_user_prompt}"
    )
    print(
        "包含 PATH_TEST_003："
        f"{'PATH_TEST_003' in client.last_user_prompt}"
    )

    for error in errors:
        print(f"错误：{error}")

    return not errors


def validate_no_anchor_gap() -> bool:
    """验证没有语义锚点时补充证据缺口说明。"""

    ranker = FakeEvidencePathRanker(
        return_anchors=False
    )

    pipeline = KGRAGPipeline(
        ranker=ranker,
        client=FakeQwenClient(),
    )

    result = pipeline.run(
        case_id="TEST_KG_RAG_003",
        candidate_disease="基底细胞癌",
        user_observation="患者描述了不明确的皮损变化。",
        top_k=2,
        max_hops=1,
    )

    expected_message = (
        "用户观察未识别出可靠语义锚点，"
        "当前图谱证据主要属于候选疾病的一般知识，"
        "不能视为用户个体的直接匹配证据。"
    )

    errors: List[str] = []

    if expected_message not in result.evidence_gap:
        errors.append(
            "未识别语义锚点时，"
            "缺少对应 evidence_gap 说明。"
        )

    print_separator()
    print(
        "KG_RAG_VALIDATION_003："
        f"{'通过' if not errors else '失败'}"
    )
    print("测试名称：无语义锚点证据缺口检查")
    print(
        "包含无锚点说明："
        f"{expected_message in result.evidence_gap}"
    )

    for error in errors:
        print(f"错误：{error}")

    return not errors


def validate_input_constraints() -> bool:
    """验证必填输入、top_k 和 max_hops 参数。"""

    pipeline = KGRAGPipeline(
        ranker=FakeEvidencePathRanker(),
        client=FakeQwenClient(),
    )

    errors: List[str] = []

    invalid_cases = [
        {
            "case_id": "",
            "candidate_disease": "基底细胞癌",
            "user_observation": "面部出现结节。",
            "top_k": 5,
            "max_hops": 2,
            "name": "空 case_id",
        },
        {
            "case_id": "TEST_KG_RAG_004",
            "candidate_disease": "",
            "user_observation": "面部出现结节。",
            "top_k": 5,
            "max_hops": 2,
            "name": "空 candidate_disease",
        },
        {
            "case_id": "TEST_KG_RAG_005",
            "candidate_disease": "基底细胞癌",
            "user_observation": "",
            "top_k": 5,
            "max_hops": 2,
            "name": "空 user_observation",
        },
        {
            "case_id": "TEST_KG_RAG_006",
            "candidate_disease": "基底细胞癌",
            "user_observation": "面部出现结节。",
            "top_k": 0,
            "max_hops": 2,
            "name": "非法 top_k",
        },
        {
            "case_id": "TEST_KG_RAG_007",
            "candidate_disease": "基底细胞癌",
            "user_observation": "面部出现结节。",
            "top_k": 5,
            "max_hops": 3,
            "name": "非法 max_hops",
        },
    ]

    for case in invalid_cases:
        try:
            pipeline.run(
                case_id=case["case_id"],
                candidate_disease=case[
                    "candidate_disease"
                ],
                user_observation=case[
                    "user_observation"
                ],
                top_k=case["top_k"],
                max_hops=case["max_hops"],
            )

            errors.append(
                f"{case['name']} 未触发 ValueError。"
            )

        except ValueError:
            pass

    print_separator()
    print(
        "KG_RAG_VALIDATION_004："
        f"{'通过' if not errors else '失败'}"
    )
    print("测试名称：输入参数约束检查")

    for error in errors:
        print(f"错误：{error}")

    return not errors


def validate_failed_result() -> bool:
    """验证 KG-RAG 失败结果结构。"""

    result = build_failed_result(
        case_id="TEST_KG_RAG_008",
        candidate_disease="基底细胞癌",
        user_observation="面部出现结节。",
        error_message="模拟 KG-RAG 运行失败",
    )

    errors: List[str] = []

    if result.method != "kg_rag":
        errors.append(
            "失败结果 method 必须为 kg_rag。"
        )

    if result.run_status != "failed":
        errors.append(
            "失败结果 run_status 必须为 failed。"
        )

    if result.error_message != (
        "模拟 KG-RAG 运行失败"
    ):
        errors.append(
            "错误信息记录不正确。"
        )

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
        "KG_RAG_VALIDATION_005："
        f"{'通过' if not errors else '失败'}"
    )
    print("测试名称：统一失败结果检查")
    print(f"run_status：{result.run_status}")
    print(
        f"error_message：{result.error_message}"
    )

    for error in errors:
        print(f"错误：{error}")

    return not errors


def main() -> int:
    results = [
        validate_success_result(),
        validate_top_k_context(),
        validate_no_anchor_gap(),
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
            "KG-RAG 主流程验证通过："
            f"{total_count} 组检查全部通过。"
        )
        return 0

    print(
        "KG-RAG 主流程验证未通过："
        f"{total_count - passed_count} 组检查失败。"
    )
    print(
        f"通过数量：{passed_count}/{total_count}"
    )

    return 1


if __name__ == "__main__":
    raise SystemExit(main())