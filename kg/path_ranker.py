"""
Knowledge graph evidence path ranking for dermatology KG-RAG.

Example:

    python kg/path_ranker.py \
        "基底细胞癌" \
        "患者面部出现光亮的珍珠样结节，表面可见细小血管。" \
        --top-k 5 \
        --max-hops 2

Scoring formula:

    total_score
    = entity_match_score
    + relation_weight_score
    + disease_match_score
    - path_length_penalty
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from kg.path_retriever import EvidencePath
from kg.path_retriever import GraphPathRetriever
from rag.semantic_anchor import SemanticAnchor
from rag.semantic_anchor import SemanticAnchorMapper


DEFAULT_CONFIG_FILE = (
    PROJECT_ROOT
    / "configs"
    / "relation_weights.yaml"
)


# 二跳路径中，第一跳“鉴别诊断”关系只提供辅助作用，
# 因此使用折扣系数，避免二跳路径因为关系数量更多而虚高。
INTERMEDIATE_RELATION_DISCOUNT = 0.25


@dataclass(frozen=True)
class RankingConfig:
    """证据路径排序配置。"""

    relation_weights: dict[str, float]
    entity_match_weight: float
    disease_match_weight: float
    hop_1_penalty: float
    hop_2_penalty: float
    default_top_k: int
    max_hops: int


@dataclass(frozen=True)
class RankedEvidencePath:
    """带评分结果的证据路径。"""

    path_id: str
    rank: int

    start_disease_id: str
    start_disease_name: str

    hop_count: int
    end_entity_id: str
    end_entity_name: str
    end_entity_type: str

    relation_chain: tuple[str, ...]

    matched_anchor_ids: tuple[str, ...]
    matched_anchor_names: tuple[str, ...]
    matched_anchor_confidences: tuple[float, ...]

    entity_match_score: float
    relation_weight_score: float
    disease_match_score: float
    path_length_penalty: float
    total_score: float

    source_names: tuple[str, ...]
    evidence_texts: tuple[str, ...]

    path: EvidencePath

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)

        result["relation_chain"] = list(
            self.relation_chain
        )
        result["matched_anchor_ids"] = list(
            self.matched_anchor_ids
        )
        result["matched_anchor_names"] = list(
            self.matched_anchor_names
        )
        result["matched_anchor_confidences"] = list(
            self.matched_anchor_confidences
        )
        result["source_names"] = list(
            self.source_names
        )
        result["evidence_texts"] = list(
            self.evidence_texts
        )
        result["path"] = self.path.to_dict()

        return result


def parse_scalar(value: str) -> Any:
    """
    将简单 YAML 标量转换成 Python 类型。

    当前配置文件只需要支持：

    - 字符串
    - 整数
    - 浮点数
    - true / false
    """

    cleaned = value.strip()

    if not cleaned:
        return ""

    lowered = cleaned.lower()

    if lowered == "true":
        return True

    if lowered == "false":
        return False

    if (
        cleaned.startswith('"')
        and cleaned.endswith('"')
    ):
        return cleaned[1:-1]

    if (
        cleaned.startswith("'")
        and cleaned.endswith("'")
    ):
        return cleaned[1:-1]

    try:
        if "." in cleaned:
            return float(cleaned)

        return int(cleaned)

    except ValueError:
        return cleaned


def load_simple_yaml(
    config_file: Path,
) -> dict[str, dict[str, Any]]:
    """
    读取本项目使用的简单 YAML 配置。

    为避免额外安装 PyYAML，本函数只解析任务三需要的
    一级分组和二级键值，不处理复杂 YAML 语法。
    """

    if not config_file.exists():
        raise FileNotFoundError(
            f"找不到路径评分配置文件：{config_file}"
        )

    sections: dict[
        str,
        dict[str, Any],
    ] = {}

    current_section: str | None = None

    content = config_file.read_text(
        encoding="utf-8-sig"
    )

    for line_number, raw_line in enumerate(
        content.splitlines(),
        start=1,
    ):
        line_without_comment = raw_line.split(
            "#",
            maxsplit=1,
        )[0]

        if not line_without_comment.strip():
            continue

        if "\t" in raw_line:
            raise ValueError(
                f"配置文件第 {line_number} 行包含 Tab，"
                "请统一使用空格缩进。"
            )

        stripped = line_without_comment.strip()

        # 一级分组，例如 relation_weights:
        if (
            not line_without_comment.startswith(" ")
            and stripped.endswith(":")
        ):
            current_section = stripped[:-1].strip()

            sections.setdefault(
                current_section,
                {},
            )
            continue

        # 本评分程序只处理二级键值。
        if current_section is None:
            continue

        if ":" not in stripped:
            continue

        key, value = stripped.split(
            ":",
            maxsplit=1,
        )

        # 跳过列表型配置，因为当前评分函数不依赖这些列表。
        if not value.strip():
            continue

        sections[current_section][
            key.strip()
        ] = parse_scalar(value)

    return sections


def load_ranking_config(
    config_file: Path = DEFAULT_CONFIG_FILE,
) -> RankingConfig:
    """读取并检查路径排序所需配置。"""

    config_data = load_simple_yaml(
        config_file
    )

    relation_weights = config_data.get(
        "relation_weights",
        {},
    )

    score_weights = config_data.get(
        "score_weights",
        {},
    )

    path_penalties = config_data.get(
        "path_length_penalties",
        {},
    )

    retrieval = config_data.get(
        "retrieval",
        {},
    )

    required_relations = {
        "has_manifestation",
        "commonly_occurs_at",
        "has_symptom",
        "differential_diagnosis",
        "recommended_examination",
        "has_risk_warning",
        "has_medical_advice",
    }

    missing_relations = (
        required_relations
        - set(relation_weights)
    )

    if missing_relations:
        raise ValueError(
            "关系权重配置缺失："
            f"{sorted(missing_relations)}"
        )

    required_score_keys = {
        "entity_match",
        "disease_match",
    }

    missing_score_keys = (
        required_score_keys
        - set(score_weights)
    )

    if missing_score_keys:
        raise ValueError(
            "评分权重配置缺失："
            f"{sorted(missing_score_keys)}"
        )

    required_penalty_keys = {
        "hop_1",
        "hop_2",
    }

    missing_penalty_keys = (
        required_penalty_keys
        - set(path_penalties)
    )

    if missing_penalty_keys:
        raise ValueError(
            "路径惩罚配置缺失："
            f"{sorted(missing_penalty_keys)}"
        )

    return RankingConfig(
        relation_weights={
            key: float(value)
            for key, value
            in relation_weights.items()
        },
        entity_match_weight=float(
            score_weights["entity_match"]
        ),
        disease_match_weight=float(
            score_weights["disease_match"]
        ),
        hop_1_penalty=float(
            path_penalties["hop_1"]
        ),
        hop_2_penalty=float(
            path_penalties["hop_2"]
        ),
        default_top_k=int(
            retrieval.get(
                "default_top_k",
                5,
            )
        ),
        max_hops=int(
            retrieval.get(
                "max_hops",
                2,
            )
        ),
    )


class EvidencePathRanker:
    """对知识图谱证据路径进行可解释评分。"""

    def __init__(
        self,
        config_file: Path = DEFAULT_CONFIG_FILE,
    ) -> None:
        self.config_file = Path(config_file)

        self.config = load_ranking_config(
            self.config_file
        )

        self.path_retriever = (
            GraphPathRetriever()
        )

        self.anchor_mapper = (
            SemanticAnchorMapper()
        )

    @staticmethod
    def _match_path_anchors(
        path: EvidencePath,
        anchors: list[SemanticAnchor],
    ) -> list[SemanticAnchor]:
        """
        找出与路径终点实体一致的语义锚点。

        例如：

        用户语义锚点：
        LF_010 珍珠样结节

        图谱路径终点：
        LF_010 珍珠样结节

        则视为实体匹配。
        """

        return [
            anchor
            for anchor in anchors
            if anchor.entity_id
            == path.end_entity_id
        ]

    def _calculate_entity_match_score(
        self,
        matched_anchors: list[
            SemanticAnchor
        ],
    ) -> float:
        """
        计算实体匹配分。

        同一路径通常只对应一个终点实体，因此取匹配锚点中
        最高置信度，再乘以实体匹配权重。
        """

        if not matched_anchors:
            return 0.0

        best_confidence = max(
            anchor.confidence
            for anchor in matched_anchors
        )

        return round(
            best_confidence
            * self.config.entity_match_weight,
            4,
        )

    def _calculate_relation_weight_score(
        self,
        path: EvidencePath,
    ) -> float:
        """
        计算关系权重分。

        一跳路径：
            直接使用该关系权重。

        二跳路径：
            最后一跳关系权重
            + 第一跳关系权重 × 折扣系数。
        """

        relation_chain = list(
            path.relation_chain
        )

        if not relation_chain:
            return 0.0

        final_relation = relation_chain[-1]

        final_relation_score = (
            self.config.relation_weights.get(
                final_relation,
                0.0,
            )
        )

        if len(relation_chain) == 1:
            return round(
                final_relation_score,
                4,
            )

        intermediate_score = sum(
            self.config.relation_weights.get(
                relation,
                0.0,
            )
            for relation
            in relation_chain[:-1]
        )

        total_relation_score = (
            final_relation_score
            + intermediate_score
            * INTERMEDIATE_RELATION_DISCOUNT
        )

        return round(
            total_relation_score,
            4,
        )

    def _calculate_disease_match_score(
        self,
        path: EvidencePath,
    ) -> float:
        """
        计算候选疾病匹配分。

        一跳路径直接描述候选疾病，获得完整疾病匹配分。

        二跳路径的最终证据属于鉴别疾病，仅获得部分疾病
        匹配分，防止其排序高于候选疾病直接证据。
        """

        if path.hop_count == 1:
            factor = 1.0
        else:
            factor = 0.70

        return round(
            self.config.disease_match_weight
            * factor,
            4,
        )

    def _calculate_path_length_penalty(
        self,
        path: EvidencePath,
    ) -> float:
        """按照路径跳数计算长度惩罚。"""

        if path.hop_count == 1:
            return round(
                self.config.hop_1_penalty,
                4,
            )

        return round(
            self.config.hop_2_penalty,
            4,
        )

    def score_path(
        self,
        path: EvidencePath,
        anchors: list[SemanticAnchor],
    ) -> RankedEvidencePath:
        """对单条证据路径进行评分。"""

        matched_anchors = (
            self._match_path_anchors(
                path,
                anchors,
            )
        )

        entity_match_score = (
            self._calculate_entity_match_score(
                matched_anchors
            )
        )

        relation_weight_score = (
            self._calculate_relation_weight_score(
                path
            )
        )

        disease_match_score = (
            self._calculate_disease_match_score(
                path
            )
        )

        path_length_penalty = (
            self._calculate_path_length_penalty(
                path
            )
        )

        total_score = round(
            entity_match_score
            + relation_weight_score
            + disease_match_score
            - path_length_penalty,
            4,
        )

        return RankedEvidencePath(
            path_id=path.path_id,
            rank=0,
            start_disease_id=(
                path.start_disease_id
            ),
            start_disease_name=(
                path.start_disease_name
            ),
            hop_count=path.hop_count,
            end_entity_id=(
                path.end_entity_id
            ),
            end_entity_name=(
                path.end_entity_name
            ),
            end_entity_type=(
                path.end_entity_type
            ),
            relation_chain=(
                path.relation_chain
            ),
            matched_anchor_ids=tuple(
                anchor.entity_id
                for anchor in matched_anchors
            ),
            matched_anchor_names=tuple(
                anchor.entity_name
                for anchor in matched_anchors
            ),
            matched_anchor_confidences=tuple(
                anchor.confidence
                for anchor in matched_anchors
            ),
            entity_match_score=(
                entity_match_score
            ),
            relation_weight_score=(
                relation_weight_score
            ),
            disease_match_score=(
                disease_match_score
            ),
            path_length_penalty=(
                path_length_penalty
            ),
            total_score=total_score,
            source_names=(
                path.source_names
            ),
            evidence_texts=(
                path.evidence_texts
            ),
            path=path,
        )

    @staticmethod
    def _with_rank(
        result: RankedEvidencePath,
        rank: int,
    ) -> RankedEvidencePath:
        """为排序结果写入名次。"""

        return RankedEvidencePath(
            path_id=result.path_id,
            rank=rank,
            start_disease_id=(
                result.start_disease_id
            ),
            start_disease_name=(
                result.start_disease_name
            ),
            hop_count=result.hop_count,
            end_entity_id=(
                result.end_entity_id
            ),
            end_entity_name=(
                result.end_entity_name
            ),
            end_entity_type=(
                result.end_entity_type
            ),
            relation_chain=(
                result.relation_chain
            ),
            matched_anchor_ids=(
                result.matched_anchor_ids
            ),
            matched_anchor_names=(
                result.matched_anchor_names
            ),
            matched_anchor_confidences=(
                result.matched_anchor_confidences
            ),
            entity_match_score=(
                result.entity_match_score
            ),
            relation_weight_score=(
                result.relation_weight_score
            ),
            disease_match_score=(
                result.disease_match_score
            ),
            path_length_penalty=(
                result.path_length_penalty
            ),
            total_score=(
                result.total_score
            ),
            source_names=(
                result.source_names
            ),
            evidence_texts=(
                result.evidence_texts
            ),
            path=result.path,
        )

    def rank(
        self,
        disease_query: str,
        observation_text: str,
        top_k: int | None = None,
        max_hops: int | None = None,
    ) -> tuple[
        list[SemanticAnchor],
        list[RankedEvidencePath],
        int,
    ]:
        """
        完成语义锚点识别、路径检索和路径排序。

        返回：

        - 语义锚点列表；
        - Top-k 排序路径；
        - 排序前的路径总数。
        """

        resolved_top_k = (
            self.config.default_top_k
            if top_k is None
            else top_k
        )

        resolved_max_hops = (
            self.config.max_hops
            if max_hops is None
            else max_hops
        )

        if resolved_top_k <= 0:
            raise ValueError(
                "top_k 必须大于 0。"
            )

        if resolved_max_hops not in {1, 2}:
            raise ValueError(
                "max_hops 当前只允许为 1 或 2。"
            )

        anchors = self.anchor_mapper.extract(
            observation_text
        )

        paths = self.path_retriever.retrieve_paths(
            disease_query=disease_query,
            max_hops=resolved_max_hops,
        )

        scored_paths = [
            self.score_path(
                path=path,
                anchors=anchors,
            )
            for path in paths
        ]

        scored_paths.sort(
            key=lambda result: (
                -result.total_score,
                -result.entity_match_score,
                -result.relation_weight_score,
                result.hop_count,
                result.path_id,
            )
        )

        top_results = scored_paths[
            :resolved_top_k
        ]

        ranked_results = [
            self._with_rank(
                result=result,
                rank=index,
            )
            for index, result
            in enumerate(
                top_results,
                start=1,
            )
        ]

        return (
            anchors,
            ranked_results,
            len(paths),
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "根据用户观察结果对皮肤病知识图谱"
            "证据路径进行可解释排序。"
        )
    )

    parser.add_argument(
        "disease",
        help=(
            "候选疾病中文名、英文名、"
            "HAM10000 标签或实体 ID"
        ),
    )

    parser.add_argument(
        "observation",
        help="用户观察文本",
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=None,
        help=(
            "返回的证据路径数量，"
            "默认读取配置文件"
        ),
    )

    parser.add_argument(
        "--max-hops",
        type=int,
        choices=[1, 2],
        default=None,
        help=(
            "最大路径跳数，默认读取配置文件"
        ),
    )

    args = parser.parse_args()

    try:
        ranker = EvidencePathRanker()

        disease = (
            ranker.path_retriever.resolve_disease(
                args.disease
            )
        )

        anchors, ranked_paths, path_count = (
            ranker.rank(
                disease_query=args.disease,
                observation_text=args.observation,
                top_k=args.top_k,
                max_hops=args.max_hops,
            )
        )

    except (
        FileNotFoundError,
        ValueError,
    ) as exc:
        print(
            f"路径排序失败：{exc}"
        )
        return 1

    output = {
        "candidate_disease": {
            "entity_id": disease["id"],
            "name_cn": disease["name_cn"],
            "name_en": disease.get(
                "name_en",
                "",
            ),
        },
        "observation_text": args.observation,
        "semantic_anchors": [
            anchor.to_dict()
            for anchor in anchors
        ],
        "retrieved_path_count": path_count,
        "returned_path_count": len(
            ranked_paths
        ),
        "ranking_formula": (
            "entity_match_score "
            "+ relation_weight_score "
            "+ disease_match_score "
            "- path_length_penalty"
        ),
        "ranked_paths": [
            result.to_dict()
            for result in ranked_paths
        ],
    }

    print(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())