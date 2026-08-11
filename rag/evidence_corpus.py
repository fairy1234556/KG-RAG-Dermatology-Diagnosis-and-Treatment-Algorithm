"""
Build a flat medical evidence corpus for the ordinary RAG baseline.

The corpus is generated from:

    kg/csv/triples.csv

Important experimental boundary:

- Only evidence text and source information are retained.
- Graph relations and entity paths are not exposed to the RAG retriever.
- The corpus is therefore a flat text collection rather than a graph index.

Run:

    python rag/evidence_corpus.py
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_TRIPLE_FILE = (
    PROJECT_ROOT
    / "kg"
    / "csv"
    / "triples.csv"
)

DEFAULT_OUTPUT_FILE = (
    PROJECT_ROOT
    / "rag"
    / "data"
    / "evidence_corpus_v1.jsonl"
)


@dataclass
class EvidenceDocument:
    """普通 RAG 使用的一条扁平文本证据。"""

    document_id: str
    text: str
    source_names: List[str]
    origin_record_ids: List[str]

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass
class CorpusStatistics:
    """语料库构建统计信息。"""

    total_rows: int
    valid_evidence_rows: int
    skipped_empty_rows: int
    merged_duplicate_rows: int
    document_count: int

    def to_dict(self) -> Dict[str, int]:
        return asdict(self)


def normalize_whitespace(text: str) -> str:
    """统一空白字符，保留原有医学语义。"""

    cleaned = (text or "").strip()

    cleaned = re.sub(
        r"\s+",
        " ",
        cleaned,
    )

    return cleaned


def append_unique(
    values: List[str],
    new_value: str,
) -> None:
    """向列表追加非空且不重复的字符串。"""

    cleaned = normalize_whitespace(
        new_value
    )

    if not cleaned:
        return

    if cleaned not in values:
        values.append(cleaned)


def read_csv_rows(
    csv_file: Path,
) -> List[Dict[str, str]]:
    """读取 CSV 文件并清理字段名和字段值。"""

    if not csv_file.exists():
        raise FileNotFoundError(
            f"找不到三元组文件：{csv_file}"
        )

    rows: List[Dict[str, str]] = []

    with csv_file.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        reader = csv.DictReader(file)

        if reader.fieldnames is None:
            raise ValueError(
                f"CSV 文件缺少表头：{csv_file}"
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


def validate_triple_headers(
    rows: List[Dict[str, str]],
) -> None:
    """检查构建文本语料所需字段。"""

    if not rows:
        raise ValueError(
            "triples.csv 中没有可用记录。"
        )

    required_fields = {
        "triple_id",
        "evidence_text",
        "source",
    }

    available_fields = set(
        rows[0].keys()
    )

    missing_fields = (
        required_fields
        - available_fields
    )

    if missing_fields:
        raise ValueError(
            "triples.csv 缺少语料构建字段："
            f"{sorted(missing_fields)}"
        )


def build_evidence_documents(
    triple_file: Path = DEFAULT_TRIPLE_FILE,
) -> Tuple[
    List[EvidenceDocument],
    CorpusStatistics,
]:
    """
    将图谱中的证据文本转换成扁平文档集合。

    去重规则：

    - 对空白归一化后的 evidence_text 去重；
    - 相同证据文本对应的来源和原始记录编号合并；
    - 不向文档写入实体关系或图谱路径。
    """

    rows = read_csv_rows(
        triple_file
    )

    validate_triple_headers(rows)

    grouped_documents: Dict[
        str,
        Dict[str, object],
    ] = {}

    valid_evidence_rows = 0
    skipped_empty_rows = 0

    for row in rows:
        evidence_text = normalize_whitespace(
            row.get(
                "evidence_text",
                "",
            )
        )

        if not evidence_text:
            skipped_empty_rows += 1
            continue

        valid_evidence_rows += 1

        # casefold 只用于生成去重键，
        # 实际输出仍保留首次出现的原始文本。
        deduplication_key = (
            evidence_text.casefold()
        )

        if (
            deduplication_key
            not in grouped_documents
        ):
            grouped_documents[
                deduplication_key
            ] = {
                "text": evidence_text,
                "source_names": [],
                "origin_record_ids": [],
            }

        grouped = grouped_documents[
            deduplication_key
        ]

        source_names = grouped[
            "source_names"
        ]

        origin_record_ids = grouped[
            "origin_record_ids"
        ]

        if not isinstance(
            source_names,
            list,
        ):
            raise TypeError(
                "source_names 内部类型错误。"
            )

        if not isinstance(
            origin_record_ids,
            list,
        ):
            raise TypeError(
                "origin_record_ids 内部类型错误。"
            )

        append_unique(
            source_names,
            row.get("source", ""),
        )

        append_unique(
            origin_record_ids,
            row.get("triple_id", ""),
        )

    sorted_groups = sorted(
        grouped_documents.values(),
        key=lambda item: (
            item["origin_record_ids"][0]
            if item["origin_record_ids"]
            else "",
            item["text"],
        ),
    )

    documents: List[
        EvidenceDocument
    ] = []

    for index, grouped in enumerate(
        sorted_groups,
        start=1,
    ):
        documents.append(
            EvidenceDocument(
                document_id=(
                    f"DOC_{index:04d}"
                ),
                text=str(
                    grouped["text"]
                ),
                source_names=list(
                    grouped["source_names"]
                ),
                origin_record_ids=list(
                    grouped[
                        "origin_record_ids"
                    ]
                ),
            )
        )

    statistics = CorpusStatistics(
        total_rows=len(rows),
        valid_evidence_rows=(
            valid_evidence_rows
        ),
        skipped_empty_rows=(
            skipped_empty_rows
        ),
        merged_duplicate_rows=(
            valid_evidence_rows
            - len(documents)
        ),
        document_count=len(documents),
    )

    return documents, statistics


def write_jsonl(
    documents: List[EvidenceDocument],
    output_file: Path,
) -> None:
    """将语料库写入 JSON Lines 文件。"""

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_file.open(
        "w",
        encoding="utf-8",
    ) as file:
        for document in documents:
            file.write(
                json.dumps(
                    document.to_dict(),
                    ensure_ascii=False,
                )
            )

            file.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "构建普通 RAG 使用的扁平医学"
            "证据文本语料库。"
        )
    )

    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_TRIPLE_FILE,
        help="输入 triples.csv 文件路径",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_FILE,
        help="输出 JSONL 文件路径",
    )

    args = parser.parse_args()

    try:
        documents, statistics = (
            build_evidence_documents(
                triple_file=args.input,
            )
        )

        if not documents:
            raise ValueError(
                "未构建出任何有效证据文档。"
            )

        write_jsonl(
            documents=documents,
            output_file=args.output,
        )

    except (
        FileNotFoundError,
        ValueError,
        TypeError,
    ) as exc:
        print(
            f"普通 RAG 语料库构建失败：{exc}"
        )
        return 1

    print(
        "普通 RAG 文本语料库构建完成。"
    )
    print(
        f"输入记录数："
        f"{statistics.total_rows}"
    )
    print(
        f"有效证据记录数："
        f"{statistics.valid_evidence_rows}"
    )
    print(
        f"跳过空证据记录数："
        f"{statistics.skipped_empty_rows}"
    )
    print(
        f"合并重复证据记录数："
        f"{statistics.merged_duplicate_rows}"
    )
    print(
        f"最终文档数："
        f"{statistics.document_count}"
    )
    print(
        f"输出文件："
        f"{args.output.resolve()}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())