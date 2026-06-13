"""
Simple query demo for the dermatology knowledge graph CSV files.

Run:
    python kg/kg_query_demo.py
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, Iterable, List, Optional


class KnowledgeGraphQuery:
    """Load CSV knowledge graph files and provide simple evidence queries."""

    def __init__(self, csv_dir: Optional[Path] = None) -> None:
        base_dir = Path(__file__).resolve().parent
        self.csv_dir = csv_dir or base_dir / "csv"

        self.entity_path = self.csv_dir / "entity_nodes.csv"
        self.triple_path = self.csv_dir / "triples.csv"
        self.source_path = self.csv_dir / "source_references.csv"

        self._check_required_files()
        self.entities = self._read_csv(self.entity_path)
        self.triples = self._read_csv(self.triple_path)
        self.sources = self._read_csv(self.source_path)

        self.entities_by_id = {
            entity["id"]: entity for entity in self.entities if entity.get("id")
        }
        self.sources_by_triple_id = self._build_sources_by_triple_id()

    def _check_required_files(self) -> None:
        """Raise a clear error if one of the required CSV files is missing."""
        missing_files = [
            path for path in (self.entity_path, self.triple_path, self.source_path)
            if not path.exists()
        ]
        if missing_files:
            missing_text = "\n".join(f"- {path}" for path in missing_files)
            raise FileNotFoundError(
                "Required CSV file(s) not found. Please check kg/csv:\n"
                f"{missing_text}"
            )

    @staticmethod
    def _strip_row(row: Dict[str, Optional[str]]) -> Dict[str, str]:
        """Strip spaces around headers and values."""
        cleaned = {}
        for key, value in row.items():
            clean_key = (key or "").strip()
            cleaned[clean_key] = (value or "").strip()
        return cleaned

    def _read_csv(self, path: Path) -> List[Dict[str, str]]:
        """Read CSV, strip fields, and skip empty rows.

        utf-8-sig is tried first as required. gb18030 is a practical fallback for
        Chinese CSV files that were saved by spreadsheet tools on Windows.
        """
        last_error: Optional[UnicodeDecodeError] = None
        for encoding in ("utf-8-sig", "gb18030"):
            rows: List[Dict[str, str]] = []
            try:
                with path.open("r", encoding=encoding, newline="") as csv_file:
                    reader = csv.DictReader(csv_file)
                    for raw_row in reader:
                        row = self._strip_row(raw_row)
                        if any(value for value in row.values()):
                            rows.append(row)
                return rows
            except UnicodeDecodeError as error:
                last_error = error

        raise UnicodeDecodeError(
            last_error.encoding,
            last_error.object,
            last_error.start,
            last_error.end,
            f"Cannot decode CSV file: {path}",
        )

    def _build_sources_by_triple_id(self) -> Dict[str, Dict[str, str]]:
        """Map each triple_id to its source reference row."""
        sources_by_triple_id: Dict[str, Dict[str, str]] = {}
        for source in self.sources:
            for triple_id in self._split_list_field(source.get("used_for_triples", "")):
                sources_by_triple_id[triple_id] = source
        return sources_by_triple_id

    @staticmethod
    def _split_list_field(value: str) -> List[str]:
        """Split comma/semicolon/Chinese comma separated aliases or IDs."""
        for separator in (";", "；", "，", "|"):
            value = value.replace(separator, ",")
        return [item.strip() for item in value.split(",") if item.strip()]

    @staticmethod
    def _norm(value: str) -> str:
        """Normalize a lookup value for case-insensitive exact matching."""
        return value.strip().lower()

    def _entity_matches(self, entity: Dict[str, str], query: str) -> bool:
        candidates = [
            entity.get("id", ""),
            entity.get("name_cn", ""),
            entity.get("name_en", ""),
        ]
        candidates.extend(self._split_list_field(entity.get("alias", "")))
        normalized_query = self._norm(query)
        return any(self._norm(candidate) == normalized_query for candidate in candidates)

    def _find_entity_ids(self, query: str, entity_type: Optional[str] = None) -> List[str]:
        """Find entity IDs by Chinese name, English name, ID, or alias."""
        matched_ids = []
        for entity in self.entities:
            if entity_type and entity.get("entity_type") != entity_type:
                continue
            if self._entity_matches(entity, query):
                matched_ids.append(entity["id"])
        return matched_ids

    def _with_source_reference(self, triple: Dict[str, str]) -> Dict[str, str]:
        """Attach source reference metadata without changing the raw CSV rows."""
        result = dict(triple)
        source_ref = self.sources_by_triple_id.get(triple.get("triple_id", ""))
        if source_ref:
            result["source_id"] = source_ref.get("source_id", "")
            result["source_type"] = source_ref.get("source_type", "")
        else:
            result["source_id"] = ""
            result["source_type"] = ""
        return result

    def _attach_sources(self, triples: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
        return [self._with_source_reference(triple) for triple in triples]

    def query_by_disease(self, disease_name: str) -> List[Dict[str, str]]:
        """Return all triples whose head is the given disease."""
        disease_ids = set(self._find_entity_ids(disease_name, "Disease"))
        if not disease_ids:
            return []
        return self._attach_sources(
            triple for triple in self.triples
            if triple.get("head_id") in disease_ids
        )

    def query_by_relation(
        self, disease_name: str, relation_en: str
    ) -> List[Dict[str, str]]:
        """Return triples for a disease filtered by English relation name."""
        normalized_relation = self._norm(relation_en)
        return [
            triple for triple in self.query_by_disease(disease_name)
            if self._norm(triple.get("relation_en", "")) == normalized_relation
        ]

    def query_by_feature(self, feature_name: str) -> List[Dict[str, str]]:
        """Reverse lookup diseases related to a lesion feature."""
        feature_ids = set(self._find_entity_ids(feature_name, "LesionFeature"))
        if not feature_ids:
            return []
        return self._attach_sources(
            triple for triple in self.triples
            if triple.get("tail_id") in feature_ids
            and triple.get("head_type") == "Disease"
        )

    def format_results(self, results: Iterable[Dict[str, str]]) -> str:
        """Format query results for terminal output."""
        rows = list(results)
        if not rows:
            return "未查询到相关结果。"

        blocks = []
        for row in rows:
            source = row.get("source", "")
            if row.get("source_id") or row.get("source_type"):
                source = (
                    f"{source} "
                    f"({row.get('source_id', '')}, {row.get('source_type', '')})"
                ).strip()

            blocks.append(
                "\n".join(
                    [
                        f"triple_id: {row.get('triple_id', '')}",
                        "证据路径: "
                        f"{row.get('head_cn', '')} — "
                        f"{row.get('relation_cn', '')} — "
                        f"{row.get('tail_cn', '')}",
                        f"relation_en: {row.get('relation_en', '')}",
                        f"source: {source}",
                        f"evidence_text: {row.get('evidence_text', '')}",
                        f"note: {row.get('note', '')}",
                    ]
                )
            )
        return "\n\n".join(blocks)


def print_section(title: str, content: str) -> None:
    print("=" * 80)
    print(title)
    print("=" * 80)
    print(content)
    print()


def main() -> None:
    try:
        kg = KnowledgeGraphQuery()
    except FileNotFoundError as error:
        print(error)
        return

    print_section(
        '示例 1: query_by_disease("黑色素瘤")',
        kg.format_results(kg.query_by_disease("黑色素瘤")),
    )
    print_section(
        '示例 2: query_by_relation("基底细胞癌", "has_manifestation")',
        kg.format_results(
            kg.query_by_relation("基底细胞癌", "has_manifestation")
        ),
    )
    print_section(
        '示例 3: query_by_feature("珍珠样结节")',
        kg.format_results(kg.query_by_feature("珍珠样结节")),
    )


if __name__ == "__main__":
    main()
