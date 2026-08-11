"""
Knowledge graph path retrieval for dermatology evidence.

Examples:

    python kg/path_retriever.py "基底细胞癌"

    python kg/path_retriever.py "基底细胞癌" --max-hops 2

    python kg/path_retriever.py "bcc" --max-hops 1

This module reads:

    kg/csv/entity_nodes.csv
    kg/csv/triples.csv

It returns one-hop evidence paths and restricted two-hop paths.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_ENTITY_FILE = (
    PROJECT_ROOT
    / "kg"
    / "csv"
    / "entity_nodes.csv"
)

DEFAULT_TRIPLE_FILE = (
    PROJECT_ROOT
    / "kg"
    / "csv"
    / "triples.csv"
)


# 当前只允许通过“鉴别诊断”关系进入二跳扩展。
DEFAULT_FIRST_HOP_EXPANSION_RELATIONS = {
    "differential_diagnosis",
}


# 从鉴别疾病节点继续检索的关系范围。
#
# 风险提示和就医建议暂时不作为二跳诊断证据，
# 避免扩展出过多低相关路径。
DEFAULT_SECOND_HOP_RELATIONS = {
    "has_manifestation",
    "commonly_occurs_at",
    "has_symptom",
    "recommended_examination",
}


@dataclass(frozen=True)
class GraphEdge:
    """知识图谱中的一条三元组边。"""

    triple_id: str

    head_id: str
    head_name: str
    head_type: str

    relation_cn: str
    relation_en: str

    tail_id: str
    tail_name: str
    tail_type: str

    source: str
    evidence_text: str
    note: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class EvidencePath:
    """从候选疾病出发的一条证据路径。"""

    path_id: str

    start_disease_id: str
    start_disease_name: str

    hop_count: int
    edges: tuple[GraphEdge, ...]

    end_entity_id: str
    end_entity_name: str
    end_entity_type: str

    relation_chain: tuple[str, ...]
    source_names: tuple[str, ...]
    evidence_texts: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)

        # asdict 会将 tuple 保留为 tuple。
        # 为了便于 JSON 输出，显式转换为 list。
        result["edges"] = [
            edge.to_dict()
            for edge in self.edges
        ]
        result["relation_chain"] = list(
            self.relation_chain
        )
        result["source_names"] = list(
            self.source_names
        )
        result["evidence_texts"] = list(
            self.evidence_texts
        )

        return result


class GraphPathRetriever:
    """从 CSV 知识图谱中检索一跳和受限二跳路径。"""

    def __init__(
        self,
        entity_file: Path = DEFAULT_ENTITY_FILE,
        triple_file: Path = DEFAULT_TRIPLE_FILE,
    ) -> None:
        self.entity_file = Path(entity_file)
        self.triple_file = Path(triple_file)

        self.entities = self._read_csv(
            self.entity_file
        )
        self.triples = self._read_csv(
            self.triple_file
        )

        self.entities_by_id = {
            row["id"]: row
            for row in self.entities
            if row.get("id")
        }

        self.edges = [
            self._row_to_edge(row)
            for row in self.triples
        ]

        self.outgoing_edges: dict[
            str,
            list[GraphEdge],
        ] = {}

        for edge in self.edges:
            self.outgoing_edges.setdefault(
                edge.head_id,
                [],
            ).append(edge)

        self.disease_entities = [
            entity
            for entity in self.entities
            if entity.get("entity_type") == "Disease"
        ]

    @staticmethod
    def _read_csv(
        path: Path,
    ) -> list[dict[str, str]]:
        """读取 CSV，并对字段名和字段值去除空白。"""

        if not path.exists():
            raise FileNotFoundError(
                f"找不到文件：{path}"
            )

        rows: list[dict[str, str]] = []

        with path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as file:
            reader = csv.DictReader(file)

            if reader.fieldnames is None:
                raise ValueError(
                    f"CSV 文件缺少表头：{path}"
                )

            for raw_row in reader:
                row = {
                    (key or "").strip():
                    (value or "").strip()
                    for key, value in raw_row.items()
                }

                if any(row.values()):
                    rows.append(row)

        return rows

    @staticmethod
    def normalize_text(
        text: str,
    ) -> str:
        """归一化疾病名称、标签和别名。"""

        normalized = (
            text or ""
        ).lower().strip()

        normalized = re.sub(
            (
                r"[\s,，。；;：:、."
                r"!！?？（）()【】\[\]"
                r"“”\"'·\-—_]+"
            ),
            "",
            normalized,
        )

        return normalized

    @staticmethod
    def _split_aliases(
        alias_text: str,
    ) -> list[str]:
        """拆分实体表中的 alias 字段。"""

        if not alias_text:
            return []

        return [
            value.strip()
            for value in re.split(
                r"[;；|,，]+",
                alias_text,
            )
            if value.strip()
        ]

    @staticmethod
    def _row_to_edge(
        row: dict[str, str],
    ) -> GraphEdge:
        """将 triples.csv 中的一行转换为 GraphEdge。"""

        required_fields = [
            "triple_id",
            "head_id",
            "head_cn",
            "head_type",
            "relation_cn",
            "relation_en",
            "tail_id",
            "tail_cn",
            "tail_type",
        ]

        missing_fields = [
            field
            for field in required_fields
            if not row.get(field)
        ]

        if missing_fields:
            raise ValueError(
                "三元组缺少必要字段："
                f"{missing_fields}；"
                f"原始记录：{row}"
            )

        return GraphEdge(
            triple_id=row["triple_id"],
            head_id=row["head_id"],
            head_name=row["head_cn"],
            head_type=row["head_type"],
            relation_cn=row["relation_cn"],
            relation_en=row["relation_en"],
            tail_id=row["tail_id"],
            tail_name=row["tail_cn"],
            tail_type=row["tail_type"],
            source=row.get("source", ""),
            evidence_text=row.get(
                "evidence_text",
                "",
            ),
            note=row.get("note", ""),
        )
    def resolve_disease(
        self,
        disease_query: str,
    ) -> dict[str, str]:
        """
        将疾病中文名、英文名、HAM10000 标签或实体 ID
        解析为标准疾病实体。

        支持示例：

        基底细胞癌
        Basal Cell Carcinoma
        bcc
        DIS_003
        光化性角化病
        表皮内癌
        """

        normalized_query = self.normalize_text(
            disease_query
        )
        disease_query_aliases = {
            self.normalize_text(
                "良性角化性病变"
            ): self.normalize_text(
                "良性角化样病变"
            ),
            self.normalize_text(
                "良性角化病变"
            ): self.normalize_text(
                "良性角化样病变"
            ),
            self.normalize_text(
                "血管性病变"
            ): self.normalize_text(
                "血管性皮损"
            ),
            self.normalize_text(
                "血管病变"
            ): self.normalize_text(
                "血管性皮损"
            ),
            self.normalize_text(
                "血管性皮肤病变"
            ): self.normalize_text(
                "血管性皮损"
            ),
        }

        normalized_query = (
            disease_query_aliases.get(
                normalized_query,
                normalized_query,
            )
        )

        if not normalized_query:
            raise ValueError(
                "候选疾病不能为空。"
            )

        matched_entities: list[
            dict[str, str]
        ] = []

        for entity in self.disease_entities:
            candidate_values = {
                entity.get("id", ""),
                entity.get("name_cn", ""),
                entity.get("name_en", ""),
            }

            candidate_values.update(
                self._split_aliases(
                    entity.get("alias", "")
                )
            )

            # 支持“光化性角化病/表皮内癌”这类复合名称。
            # 将斜杠两侧的名称作为独立候选名称参与匹配。
            for name_field in (
                "name_cn",
                "name_en",
            ):
                standard_name = entity.get(
                    name_field,
                    "",
                )

                name_parts = re.split(
                    r"[/／]+",
                    standard_name,
                )

                candidate_values.update(
                    part.strip()
                    for part in name_parts
                    if part.strip()
                )

            normalized_values = {
                self.normalize_text(value)
                for value in candidate_values
                if value
            }

            if normalized_query in normalized_values:
                matched_entities.append(entity)

        if not matched_entities:
            available_diseases = "、".join(
                entity.get("name_cn", "")
                for entity in self.disease_entities
                if entity.get("name_cn")
            )

            raise ValueError(
                f"未找到候选疾病：{disease_query}。"
                f"当前可用疾病包括：{available_diseases}"
            )

        if len(matched_entities) > 1:
            matched_names = [
                entity.get("name_cn", "")
                for entity in matched_entities
            ]

            raise ValueError(
                "候选疾病匹配到多个实体："
                f"{matched_names}"
            )

        return matched_entities[0]

    @staticmethod
    def _unique_non_empty(
        values: Iterable[str],
    ) -> tuple[str, ...]:
        """保留顺序并去除空值及重复值。"""

        unique_values: list[str] = []
        seen: set[str] = set()

        for value in values:
            cleaned = value.strip()

            if not cleaned:
                continue

            if cleaned in seen:
                continue

            seen.add(cleaned)
            unique_values.append(cleaned)

        return tuple(unique_values)

    @staticmethod
    def _build_path_id(
        edges: tuple[GraphEdge, ...],
    ) -> str:
        """根据路径中的三元组 ID 生成稳定路径编号。"""

        triple_ids = [
            edge.triple_id
            for edge in edges
        ]

        return "PATH_" + "_".join(
            triple_ids
        )

    def _build_path(
        self,
        start_disease: dict[str, str],
        edges: tuple[GraphEdge, ...],
    ) -> EvidencePath:
        """由一条或多条边构造 EvidencePath。"""

        if not edges:
            raise ValueError(
                "不能使用空边列表构造路径。"
            )

        last_edge = edges[-1]

        return EvidencePath(
            path_id=self._build_path_id(edges),
            start_disease_id=start_disease["id"],
            start_disease_name=start_disease[
                "name_cn"
            ],
            hop_count=len(edges),
            edges=edges,
            end_entity_id=last_edge.tail_id,
            end_entity_name=last_edge.tail_name,
            end_entity_type=last_edge.tail_type,
            relation_chain=tuple(
                edge.relation_en
                for edge in edges
            ),
            source_names=self._unique_non_empty(
                edge.source
                for edge in edges
            ),
            evidence_texts=self._unique_non_empty(
                edge.evidence_text
                for edge in edges
            ),
        )

    def retrieve_one_hop_paths(
        self,
        disease_query: str,
    ) -> list[EvidencePath]:
        """返回候选疾病的所有一跳路径。"""

        disease = self.resolve_disease(
            disease_query
        )

        disease_id = disease["id"]

        edges = self.outgoing_edges.get(
            disease_id,
            [],
        )

        paths = [
            self._build_path(
                start_disease=disease,
                edges=(edge,),
            )
            for edge in edges
        ]

        return sorted(
            paths,
            key=lambda path: (
                path.edges[0].relation_en,
                path.end_entity_id,
                path.path_id,
            ),
        )

    def retrieve_two_hop_paths(
        self,
        disease_query: str,
        first_hop_relations: (
            Iterable[str] | None
        ) = None,
        second_hop_relations: (
            Iterable[str] | None
        ) = None,
    ) -> list[EvidencePath]:
        """
        返回受限二跳路径。

        默认路径形式：

        候选疾病
        → 鉴别诊断
        → 鉴别疾病
        → 表现/部位/症状/检查
        → 证据实体
        """

        disease = self.resolve_disease(
            disease_query
        )

        allowed_first_relations = set(
            first_hop_relations
            or DEFAULT_FIRST_HOP_EXPANSION_RELATIONS
        )

        allowed_second_relations = set(
            second_hop_relations
            or DEFAULT_SECOND_HOP_RELATIONS
        )

        first_edges = self.outgoing_edges.get(
            disease["id"],
            [],
        )

        paths: list[EvidencePath] = []

        for first_edge in first_edges:
            if (
                first_edge.relation_en
                not in allowed_first_relations
            ):
                continue

            # 当前二跳扩展的中间节点必须是疾病。
            if first_edge.tail_type != "Disease":
                continue

            second_edges = self.outgoing_edges.get(
                first_edge.tail_id,
                [],
            )

            for second_edge in second_edges:
                if (
                    second_edge.relation_en
                    not in allowed_second_relations
                ):
                    continue

                edges = (
                    first_edge,
                    second_edge,
                )

                paths.append(
                    self._build_path(
                        start_disease=disease,
                        edges=edges,
                    )
                )

        return sorted(
            paths,
            key=lambda path: (
                path.relation_chain,
                path.end_entity_id,
                path.path_id,
            ),
        )

    def retrieve_paths(
        self,
        disease_query: str,
        max_hops: int = 2,
    ) -> list[EvidencePath]:
        """统一返回一跳路径和可选的二跳路径。"""

        if max_hops not in {1, 2}:
            raise ValueError(
                "max_hops 当前只允许设置为 1 或 2。"
            )

        paths = self.retrieve_one_hop_paths(
            disease_query
        )

        if max_hops == 2:
            paths.extend(
                self.retrieve_two_hop_paths(
                    disease_query
                )
            )

        # 使用 path_id 去重，避免重复路径。
        unique_paths: dict[
            str,
            EvidencePath,
        ] = {}

        for path in paths:
            unique_paths[path.path_id] = path

        return list(unique_paths.values())


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "检索候选皮肤病的一跳和"
            "受限二跳知识图谱证据路径。"
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
        "--max-hops",
        type=int,
        choices=[1, 2],
        default=2,
        help=(
            "最大路径跳数，当前支持 1 或 2，"
            "默认值为 2"
        ),
    )

    args = parser.parse_args()

    try:
        retriever = GraphPathRetriever()

        disease = retriever.resolve_disease(
            args.disease
        )

        paths = retriever.retrieve_paths(
            disease_query=args.disease,
            max_hops=args.max_hops,
        )

    except (
        FileNotFoundError,
        ValueError,
    ) as exc:
        print(
            f"路径检索失败：{exc}"
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
            "alias": disease.get(
                "alias",
                "",
            ),
        },
        "max_hops": args.max_hops,
        "path_count": len(paths),
        "paths": [
            path.to_dict()
            for path in paths
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