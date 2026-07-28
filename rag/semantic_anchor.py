"""
Semantic anchor recognition and entity mapping for dermatology observations.

Example:
    python rag/semantic_anchor.py \
        "患者脸上出现光亮的珍珠样结节，表面可见细小血管。"

This module maps non-standard user descriptions to standard entities in
kg/csv/entity_nodes.csv.
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

DEFAULT_ALIAS_FILE = (
    PROJECT_ROOT
    / "kg"
    / "csv"
    / "entity_aliases.csv"
)


# 任务二 V1.0 只从用户观察文本中识别以下实体类型。
#
# RiskWarning 和 MedicalAdvice 是知识图谱提供给生成模型的补充信息，
# 不属于用户观察文本中的语义锚点，因此不参与实体映射。
DEFAULT_ENTITY_TYPES = {
    "Disease",
    "LesionFeature",
    "AnatomicalSite",
    "Symptom",
    "Examination",
}


@dataclass(frozen=True)
class SemanticAnchor:
    """从用户文本中识别出的标准知识图谱实体。"""

    entity_id: str
    entity_name: str
    entity_type: str
    matched_text: str
    normalized_alias: str
    match_method: str
    confidence: float
    source: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class AliasRecord:
    """内部使用的同义表达索引记录。"""

    alias_text: str
    normalized_alias: str
    entity_id: str
    entity_name: str
    entity_type: str
    source: str
    base_confidence: float


class SemanticAnchorMapper:
    """
    使用标准实体名称和同义词表完成语义锚点识别。

    数据来源包括：

    1. entity_nodes.csv 中的标准中文名称；
    2. entity_nodes.csv 中的标准英文名称；
    3. entity_nodes.csv 中已有的 alias；
    4. entity_aliases.csv 中维护的口语化表达。
    """

    def __init__(
        self,
        entity_file: Path = DEFAULT_ENTITY_FILE,
        alias_file: Path = DEFAULT_ALIAS_FILE,
    ) -> None:
        self.entity_file = Path(entity_file)
        self.alias_file = Path(alias_file)

        self.entities = self._read_csv(
            self.entity_file
        )

        self.entities_by_id = {
            row["id"]: row
            for row in self.entities
            if row.get("id")
        }

        self.alias_records = (
            self._build_alias_index()
        )

    @staticmethod
    def _read_csv(
        path: Path,
    ) -> list[dict[str, str]]:
        """
        读取 CSV 文件。

        使用 utf-8-sig 是为了兼容 Excel 保存时可能出现的 BOM。
        """

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
                    for key, value
                    in raw_row.items()
                }

                if any(row.values()):
                    rows.append(row)

        return rows

    @staticmethod
    def normalize_text(
        text: str,
    ) -> str:
        """
        对文本进行归一化。

        会去除：

        - 空格；
        - 中英文逗号；
        - 句号；
        - 分号；
        - 冒号；
        - 括号；
        - 引号；
        - 横线等常见标点。

        因此下面两种输入会被视为相同：

        患者脸上出现结节
        患 者脸上出现结节
        """

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
    def _split_builtin_aliases(
        alias_text: str,
    ) -> list[str]:
        """
        拆分 entity_nodes.csv 中的 alias 字段。

        支持：

        visible blood vessels; telangiectasia

        或：

        visible blood vessels|telangiectasia
        """

        if not alias_text:
            return []

        return [
            item.strip()
            for item in re.split(
                r"[;；|]+",
                alias_text,
            )
            if item.strip()
        ]

    def _make_alias_record(
        self,
        alias_text: str,
        entity: dict[str, str],
        source: str,
        base_confidence: float,
    ) -> AliasRecord | None:
        """
        创建一条有效的同义词索引记录。
        """

        normalized_alias = (
            self.normalize_text(alias_text)
        )

        # 单字符表达容易引发误匹配。
        # 例如仅根据“红”或“痒”进行映射不够可靠。
        if len(normalized_alias) < 2:
            return None

        entity_id = entity.get(
            "id",
            "",
        )

        entity_name = entity.get(
            "name_cn",
            "",
        )

        entity_type = entity.get(
            "entity_type",
            "",
        )

        if (
            not entity_id
            or not entity_name
            or not entity_type
        ):
            return None

        return AliasRecord(
            alias_text=alias_text.strip(),
            normalized_alias=normalized_alias,
            entity_id=entity_id,
            entity_name=entity_name,
            entity_type=entity_type,
            source=source,
            base_confidence=base_confidence,
        )

    def _build_alias_index(
        self,
    ) -> list[AliasRecord]:
        """
        建立同义表达索引。

        这里只为 DEFAULT_ENTITY_TYPES 中的实体建立索引。

        这样可以避免：

        dermatology evaluation
        -> ADV_004
        -> ADV_005
        -> ADV_006
        -> ADV_007

        这类 MedicalAdvice 通用别名产生冲突。
        """

        candidate_records: list[
            AliasRecord
        ] = []

        # -------------------------------------------------
        # 第一部分：读取 entity_nodes.csv
        # -------------------------------------------------

        for entity in self.entities:
            entity_id = entity.get(
                "id",
                "",
            )

            entity_name = entity.get(
                "name_cn",
                "",
            )

            entity_type = entity.get(
                "entity_type",
                "",
            )

            # 关键修复：
            # 只为任务二支持的实体类型建立索引。
            if (
                entity_type
                not in DEFAULT_ENTITY_TYPES
            ):
                continue

            if (
                not entity_id
                or not entity_name
            ):
                continue

            # 标准中文名称
            name_cn_record = (
                self._make_alias_record(
                    alias_text=entity_name,
                    entity=entity,
                    source=(
                        "standard_name_cn"
                    ),
                    base_confidence=1.00,
                )
            )

            if name_cn_record is not None:
                candidate_records.append(
                    name_cn_record
                )

            # 标准英文名称
            name_en = entity.get(
                "name_en",
                "",
            )

            if name_en:
                name_en_record = (
                    self._make_alias_record(
                        alias_text=name_en,
                        entity=entity,
                        source=(
                            "standard_name_en"
                        ),
                        base_confidence=0.95,
                    )
                )

                if (
                    name_en_record
                    is not None
                ):
                    candidate_records.append(
                        name_en_record
                    )

            # entity_nodes.csv 中已有的 alias
            builtin_aliases = (
                self._split_builtin_aliases(
                    entity.get(
                        "alias",
                        "",
                    )
                )
            )

            for builtin_alias in (
                builtin_aliases
            ):
                alias_record = (
                    self._make_alias_record(
                        alias_text=(
                            builtin_alias
                        ),
                        entity=entity,
                        source=(
                            "entity_nodes_alias"
                        ),
                        base_confidence=0.90,
                    )
                )

                if alias_record is not None:
                    candidate_records.append(
                        alias_record
                    )

        # -------------------------------------------------
        # 第二部分：读取 entity_aliases.csv
        # -------------------------------------------------

        custom_aliases = self._read_csv(
            self.alias_file
        )

        for alias_row in custom_aliases:
            alias_text = alias_row.get(
                "alias_text",
                "",
            )

            entity_id = alias_row.get(
                "entity_id",
                "",
            )

            # 跳过完全空白的行
            if (
                not alias_text
                and not entity_id
            ):
                continue

            if not alias_text:
                raise ValueError(
                    (
                        "自定义同义词缺少 "
                        f"alias_text：{alias_row}"
                    )
                )

            if not entity_id:
                raise ValueError(
                    (
                        "自定义同义词缺少 "
                        f"entity_id：{alias_text}"
                    )
                )

            if (
                entity_id
                not in self.entities_by_id
            ):
                raise ValueError(
                    (
                        "同义词引用了不存在的实体："
                        f"{alias_text} "
                        f"-> {entity_id}"
                    )
                )

            entity = (
                self.entities_by_id[
                    entity_id
                ]
            )

            # 自定义同义词同样只处理
            # 任务二支持的实体类型。
            if (
                entity.get(
                    "entity_type",
                    "",
                )
                not in DEFAULT_ENTITY_TYPES
            ):
                continue

            alias_record = (
                self._make_alias_record(
                    alias_text=alias_text,
                    entity=entity,
                    source="custom_alias",
                    base_confidence=0.96,
                )
            )

            if alias_record is not None:
                candidate_records.append(
                    alias_record
                )

        # -------------------------------------------------
        # 第三部分：冲突检查与去重
        # -------------------------------------------------

        alias_to_entity: dict[
            str,
            str,
        ] = {}

        alias_to_record: dict[
            tuple[str, str],
            AliasRecord,
        ] = {}

        for record in candidate_records:
            existing_entity_id = (
                alias_to_entity.get(
                    record.normalized_alias
                )
            )

            # 同一个同义表达不能映射到两个不同实体。
            if (
                existing_entity_id
                is not None
                and existing_entity_id
                != record.entity_id
            ):
                raise ValueError(
                    (
                        "发现一个同义表达被映射"
                        "到不同实体："
                        f"{record.alias_text} "
                        f"-> "
                        f"{existing_entity_id} "
                        f"/ {record.entity_id}"
                    )
                )

            alias_to_entity[
                record.normalized_alias
            ] = record.entity_id

            # 如果同一个表达以不同来源重复映射到
            # 同一个实体，仅保留置信度最高的一条。
            key = (
                record.normalized_alias,
                record.entity_id,
            )

            existing_record = (
                alias_to_record.get(key)
            )

            if (
                existing_record is None
                or record.base_confidence
                > existing_record.base_confidence
            ):
                alias_to_record[key] = (
                    record
                )

        records = list(
            alias_to_record.values()
        )

        # 优先匹配更长、更具体的表达。
        #
        # 例如：
        # “表面可见细小血管”
        # 应优先于：
        # “细小血管”
        records.sort(
            key=lambda item: (
                len(
                    item.normalized_alias
                ),
                item.base_confidence,
            ),
            reverse=True,
        )

        return records

    def extract(
        self,
        text: str,
        entity_types: (
            Iterable[str] | None
        ) = None,
    ) -> list[SemanticAnchor]:
        """
        从用户输入中识别语义锚点。
        """

        if not text or not text.strip():
            return []

        if entity_types is None:
            allowed_types = set(
                DEFAULT_ENTITY_TYPES
            )
        else:
            allowed_types = set(
                entity_types
            )

        normalized_text = (
            self.normalize_text(text)
        )

        if not normalized_text:
            return []

        best_by_entity: dict[
            str,
            SemanticAnchor,
        ] = {}

        for record in self.alias_records:
            if (
                record.entity_type
                not in allowed_types
            ):
                continue

            if (
                record.normalized_alias
                not in normalized_text
            ):
                continue

            if (
                record.normalized_alias
                == normalized_text
            ):
                match_method = "exact"
                confidence = (
                    record.base_confidence
                )
            else:
                match_method = "substring"
                confidence = max(
                    0.0,
                    record.base_confidence
                    - 0.04,
                )

            anchor = SemanticAnchor(
                entity_id=record.entity_id,
                entity_name=(
                    record.entity_name
                ),
                entity_type=(
                    record.entity_type
                ),
                matched_text=(
                    record.alias_text
                ),
                normalized_alias=(
                    record.normalized_alias
                ),
                match_method=match_method,
                confidence=round(
                    confidence,
                    2,
                ),
                source=record.source,
            )

            existing = (
                best_by_entity.get(
                    record.entity_id
                )
            )

            if existing is None:
                best_by_entity[
                    record.entity_id
                ] = anchor
                continue

            existing_rank = (
                existing.confidence,
                len(
                    existing.normalized_alias
                ),
            )

            new_rank = (
                anchor.confidence,
                len(
                    anchor.normalized_alias
                ),
            )

            if new_rank > existing_rank:
                best_by_entity[
                    record.entity_id
                ] = anchor

        type_order = {
            "Disease": 0,
            "LesionFeature": 1,
            "AnatomicalSite": 2,
            "Symptom": 3,
            "Examination": 4,
        }

        return sorted(
            best_by_entity.values(),
            key=lambda item: (
                type_order.get(
                    item.entity_type,
                    99,
                ),
                item.entity_id,
            ),
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "识别皮肤病观察文本中的"
            "语义锚点。"
        )
    )

    parser.add_argument(
        "text",
        help=(
            "需要进行语义锚点识别的"
            "观察文本"
        ),
    )

    args = parser.parse_args()

    try:
        mapper = SemanticAnchorMapper()

        anchors = mapper.extract(
            args.text
        )

    except (
        FileNotFoundError,
        ValueError,
    ) as exc:
        print(
            (
                "语义锚点识别初始化失败："
                f"{exc}"
            )
        )
        return 1

    print(
        json.dumps(
            [
                anchor.to_dict()
                for anchor in anchors
            ],
            ensure_ascii=False,
            indent=2,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())