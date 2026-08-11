"""
Validate graph path retrieval and evidence ranking.

Run:

    python experiments/validate_path_ranking.py
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from kg.path_ranker import EvidencePathRanker
from kg.path_ranker import RankedEvidencePath
from kg.path_retriever import GraphPathRetriever


@dataclass(frozen=True)
class RankingTestCase:
    """路径排序测试样例。"""

    case_id: str
    case_name: str
    disease: str
    observation: str
    expected_entity_ids: tuple[str, ...]
    top_k: int = 5
    max_hops: int = 2


RANKING_CASES = (
    RankingTestCase(
        case_id="RANK_001",
        case_name="基底细胞癌典型证据排序",
        disease="基底细胞癌",
        observation=(
            "患者面部出现光亮的珍珠样结节，"
            "表面可见细小血管。"
        ),
        expected_entity_ids=(
            "LF_010",
            "LF_011",
            "SITE_005",
        ),
    ),
    RankingTestCase(
        case_id="RANK_002",
        case_name="黑色素瘤典型证据排序",
        disease="黑色素瘤",
        observation=(
            "皮损形态不对称，边界不规则，"
            "并可见多种颜色。"
        ),
        expected_entity_ids=(
            "LF_001",
            "LF_002",
            "LF_003",
        ),
    ),
    RankingTestCase(
        case_id="RANK_003",
        case_name="黑色素细胞痣典型证据排序",
        disease="黑色素细胞痣",
        observation=(
            "皮损整体较对称，边界规则，"
            "颜色相对均匀。"
        ),
        expected_entity_ids=(
            "LF_006",
            "LF_007",
            "LF_009",
        ),
    ),
    RankingTestCase(
        case_id="RANK_004",
        case_name="光化性角化病典型证据排序",
        disease="光化性角化病",
        observation=(
            "日光暴露部位出现粗糙并伴有鳞屑的"
            "红色斑片。"
        ),
        expected_entity_ids=(
            "LF_015",
            "LF_017",
            "SITE_006",
        ),
    ),
)


def print_separator() -> None:
    print("=" * 70)


def score_is_consistent(
    result: RankedEvidencePath,
) -> bool:
    """
    检查总分是否等于各子项之和。

    total_score
    = entity_match_score
    + relation_weight_score
    + disease_match_score
    - path_length_penalty
    """

    calculated_score = round(
        result.entity_match_score
        + result.relation_weight_score
        + result.disease_match_score
        - result.path_length_penalty,
        4,
    )

    return (
        abs(
            calculated_score
            - result.total_score
        )
        < 0.0001
    )


def validate_ranking_case(
    ranker: EvidencePathRanker,
    case: RankingTestCase,
) -> tuple[bool, list[str]]:
    """验证单个典型证据排序样例。"""

    errors: list[str] = []

    anchors, ranked_paths, retrieved_count = (
        ranker.rank(
            disease_query=case.disease,
            observation_text=case.observation,
            top_k=case.top_k,
            max_hops=case.max_hops,
        )
    )

    anchor_ids = {
        anchor.entity_id
        for anchor in anchors
    }

    ranked_entity_ids = [
        result.end_entity_id
        for result in ranked_paths
    ]

    expected_ids = set(
        case.expected_entity_ids
    )

    missing_anchor_ids = (
        expected_ids
        - anchor_ids
    )

    if missing_anchor_ids:
        errors.append(
            "语义锚点缺失："
            f"{sorted(missing_anchor_ids)}"
        )

    missing_ranked_ids = (
        expected_ids
        - set(ranked_entity_ids)
    )

    if missing_ranked_ids:
        errors.append(
            "预期证据未进入 Top-k："
            f"{sorted(missing_ranked_ids)}"
        )

    if retrieved_count <= 0:
        errors.append(
            "没有检索到任何图谱路径。"
        )

    if not ranked_paths:
        errors.append(
            "路径排序结果为空。"
        )

    expected_ranks = list(
        range(
            1,
            len(ranked_paths) + 1,
        )
    )

    actual_ranks = [
        result.rank
        for result in ranked_paths
    ]

    if actual_ranks != expected_ranks:
        errors.append(
            "排序名次不连续："
            f"{actual_ranks}"
        )

    for result in ranked_paths:
        if not score_is_consistent(result):
            errors.append(
                f"{result.path_id} 的总分分解不一致。"
            )

        if (
            result.end_entity_id
            in expected_ids
            and result.end_entity_id
            not in result.matched_anchor_ids
        ):
            errors.append(
                f"{result.end_entity_id} 已进入排序，"
                "但没有记录对应语义锚点。"
            )

    print_separator()
    print(
        f"{case.case_id}："
        f"{'通过' if not errors else '失败'}"
    )
    print(f"测试名称：{case.case_name}")
    print(f"候选疾病：{case.disease}")
    print(f"用户观察：{case.observation}")
    print(
        "识别锚点："
        f"{sorted(anchor_ids)}"
    )
    print(
        "预期实体："
        f"{sorted(expected_ids)}"
    )
    print(
        "Top-k 实体："
        f"{ranked_entity_ids}"
    )
    print(
        f"检索路径总数：{retrieved_count}"
    )

    for result in ranked_paths:
        matched_text = (
            ", ".join(
                result.matched_anchor_names
            )
            if result.matched_anchor_names
            else "无直接锚点"
        )

        print(
            f"- Rank {result.rank}: "
            f"{result.end_entity_name} "
            f"({result.end_entity_id}) | "
            f"得分={result.total_score:.4f} | "
            f"匹配={matched_text} | "
            f"跳数={result.hop_count}"
        )

    for error in errors:
        print(f"错误：{error}")

    return not errors, errors


def validate_two_hop_expansion(
    retriever: GraphPathRetriever,
) -> tuple[bool, list[str]]:
    """验证鉴别诊断关系的受限二跳扩展。"""

    errors: list[str] = []

    one_hop_paths = retriever.retrieve_paths(
        disease_query="基底细胞癌",
        max_hops=1,
    )

    two_hop_paths = retriever.retrieve_paths(
        disease_query="基底细胞癌",
        max_hops=2,
    )

    expanded_paths = [
        path
        for path in two_hop_paths
        if path.hop_count == 2
    ]

    if not expanded_paths:
        errors.append(
            "没有检索到任何二跳路径。"
        )

    if len(two_hop_paths) <= len(one_hop_paths):
        errors.append(
            "启用二跳扩展后，路径数量没有增加。"
        )

    for path in expanded_paths:
        if len(path.relation_chain) != 2:
            errors.append(
                f"{path.path_id} 的关系链长度不为 2。"
            )
            continue

        if (
            path.relation_chain[0]
            != "differential_diagnosis"
        ):
            errors.append(
                f"{path.path_id} 的第一跳不是"
                " differential_diagnosis。"
            )

        if path.edges[0].tail_type != "Disease":
            errors.append(
                f"{path.path_id} 的中间节点不是疾病实体。"
            )

        if not path.source_names:
            errors.append(
                f"{path.path_id} 缺少来源信息。"
            )

    print_separator()
    print(
        "RANK_005："
        f"{'通过' if not errors else '失败'}"
    )
    print("测试名称：受限二跳鉴别路径扩展")
    print(
        f"一跳路径数量：{len(one_hop_paths)}"
    )
    print(
        f"包含二跳后的路径数量：{len(two_hop_paths)}"
    )
    print(
        f"二跳路径数量：{len(expanded_paths)}"
    )

    for path in expanded_paths[:5]:
        middle_entity = (
            path.edges[0].tail_name
        )

        print(
            "- "
            f"{path.start_disease_name}"
            f" → {path.edges[0].relation_cn}"
            f" → {middle_entity}"
            f" → {path.edges[1].relation_cn}"
            f" → {path.end_entity_name}"
        )

    for error in errors:
        print(f"错误：{error}")

    return not errors, errors


def validate_insufficient_evidence(
    ranker: EvidencePathRanker,
) -> tuple[bool, list[str]]:
    """
    验证观察信息不足时，不产生伪实体匹配。

    系统仍然可以返回候选疾病的图谱路径，但这些路径不应
    被标记为与用户语义锚点直接匹配。
    """

    errors: list[str] = []

    observation = (
        "皮损呈红色，但没有提供形态、"
        "部位和变化情况。"
    )

    anchors, ranked_paths, retrieved_count = (
        ranker.rank(
            disease_query="基底细胞癌",
            observation_text=observation,
            top_k=5,
            max_hops=2,
        )
    )

    if anchors:
        errors.append(
            "模糊观察文本不应识别出语义锚点，"
            f"实际得到："
            f"{[anchor.entity_id for anchor in anchors]}"
        )

    falsely_matched_paths = [
        result
        for result in ranked_paths
        if result.matched_anchor_ids
    ]

    if falsely_matched_paths:
        falsely_matched_path_ids = [
            result.path_id
            for result in falsely_matched_paths
        ]

        errors.append(
            "存在没有文本依据却被标记为实体匹配的路径："
            f"{falsely_matched_path_ids}"
        )

    if retrieved_count <= 0:
        errors.append(
            "候选疾病的图谱路径检索结果为空。"
        )

    for result in ranked_paths:
        if result.entity_match_score != 0.0:
            errors.append(
                f"{result.path_id} 的实体匹配分应为 0，"
                f"实际为 {result.entity_match_score}。"
            )

        if not score_is_consistent(result):
            errors.append(
                f"{result.path_id} 的总分分解不一致。"
            )

    print_separator()
    print(
        "RANK_006："
        f"{'通过' if not errors else '失败'}"
    )
    print("测试名称：证据不足时不强制匹配")
    print(f"用户观察：{observation}")
    print(
        "识别锚点："
        f"{[anchor.entity_id for anchor in anchors]}"
    )
    print(
        f"检索路径总数：{retrieved_count}"
    )

    for result in ranked_paths:
        print(
            f"- Rank {result.rank}: "
            f"{result.end_entity_name} "
            f"({result.end_entity_id}) | "
            f"实体匹配分={result.entity_match_score:.4f} | "
            f"总分={result.total_score:.4f}"
        )

    for error in errors:
        print(f"错误：{error}")

    return not errors, errors


def main() -> int:
    try:
        ranker = EvidencePathRanker()
        retriever = GraphPathRetriever()

    except (
        FileNotFoundError,
        ValueError,
    ) as exc:
        print(
            f"初始化失败：{exc}"
        )
        return 1

    passed_count = 0
    failed_cases: list[str] = []

    for case in RANKING_CASES:
        try:
            passed, _ = validate_ranking_case(
                ranker=ranker,
                case=case,
            )

        except Exception as exc:
            passed = False

            print_separator()
            print(f"{case.case_id}：失败")
            print(f"测试名称：{case.case_name}")
            print(f"运行异常：{exc}")

        if passed:
            passed_count += 1
        else:
            failed_cases.append(case.case_id)

    try:
        passed, _ = validate_two_hop_expansion(
            retriever
        )

    except Exception as exc:
        passed = False

        print_separator()
        print("RANK_005：失败")
        print("测试名称：受限二跳鉴别路径扩展")
        print(f"运行异常：{exc}")

    if passed:
        passed_count += 1
    else:
        failed_cases.append("RANK_005")

    try:
        passed, _ = validate_insufficient_evidence(
            ranker
        )

    except Exception as exc:
        passed = False

        print_separator()
        print("RANK_006：失败")
        print("测试名称：证据不足时不强制匹配")
        print(f"运行异常：{exc}")

    if passed:
        passed_count += 1
    else:
        failed_cases.append("RANK_006")

    print_separator()

    total_count = 6

    if not failed_cases:
        print(
            "路径检索与排序验证通过："
            f"{total_count} 组检查全部通过。"
        )
        return 0

    print(
        "路径检索与排序验证未通过："
        f"{len(failed_cases)} 组检查失败。"
    )
    print(
        f"失败项：{failed_cases}"
    )
    print(
        f"通过数量：{passed_count}/{total_count}"
    )

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
