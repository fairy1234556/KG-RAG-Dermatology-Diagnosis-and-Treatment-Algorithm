from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

METADATA_PATH = ROOT / "data" / "external" / "pad_ufes_20" / "metadata.csv"
MAPPING_PATH = (
    ROOT
    / "experiments"
    / "mappings"
    / "pad_ufes_20_kg_mapping_v1.csv"
)
OUTPUT_DIR = ROOT / "experiments" / "results" / "kg_coverage_v1"

CORE_FIELDS = [
    "itch",
    "grew",
    "hurt",
    "changed",
    "bleed",
    "elevation",
    "region",
]

VALID_CLASSES = {"EXACT", "PARTIAL", "UNMAPPED"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def normalize_value(field: str, value: str | None) -> str:
    value = (value or "").strip()

    if not value:
        return "<EMPTY>"

    if field == "region":
        return value.upper()

    return value


def load_mapping_rules() -> dict[tuple[str, str], dict[str, str]]:
    rows = read_csv(MAPPING_PATH)

    rules: dict[tuple[str, str], dict[str, str]] = {}

    for row in rows:
        field = row["source_field"].strip()
        value = row["source_value"].strip()
        coverage_class = row["coverage_class"].strip()

        if coverage_class not in VALID_CLASSES:
            raise ValueError(
                f"Invalid coverage_class={coverage_class!r} "
                f"for {field}/{value}"
            )

        key = (field, value)

        if key in rules:
            raise ValueError(f"Duplicate mapping rule: {key}")

        rules[key] = row

    return rules


def find_rule(
    rules: dict[tuple[str, str], dict[str, str]],
    field: str,
    value: str,
) -> dict[str, str] | None:
    exact_key = (field, value)
    wildcard_key = (field, "*")

    if exact_key in rules:
        return rules[exact_key]

    if wildcard_key in rules:
        return rules[wildcard_key]

    return None


def safe_rate(num: int, den: int) -> float:
    if den == 0:
        return 0.0
    return round(num / den, 4)


def main() -> None:
    if not METADATA_PATH.exists():
        raise FileNotFoundError(
            f"PAD-UFES-20 metadata not found: {METADATA_PATH}"
        )

    if not MAPPING_PATH.exists():
        raise FileNotFoundError(
            f"Mapping file not found: {MAPPING_PATH}"
        )

    metadata = read_csv(METADATA_PATH)
    rules = load_mapping_rules()

    if not metadata:
        raise ValueError("metadata.csv is empty")

    missing_columns = [
        field for field in CORE_FIELDS if field not in metadata[0]
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required metadata columns: {missing_columns}"
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    class_counts = Counter()
    pilot_usable_counts = Counter()
    field_class_counts: dict[str, Counter] = defaultdict(Counter)
    field_value_counts: dict[str, Counter] = defaultdict(Counter)

    detail_rows: list[dict[str, object]] = []

    for field in CORE_FIELDS:
        values = [
            normalize_value(field, row.get(field))
            for row in metadata
        ]

        field_value_counts[field].update(values)

        for value, count in sorted(
            field_value_counts[field].items(),
            key=lambda item: (-item[1], item[0]),
        ):
            rule = find_rule(rules, field, value)

            if rule is None:
                coverage_class = "MISSING_MAPPING_RULE"
                target_entity_id = ""
                target_entity_cn = ""
                mapping_relation = ""
                pilot_usable = "no"
                rationale = (
                    "Dataset value exists but no mapping rule "
                    "has been frozen for it."
                )
            else:
                coverage_class = rule["coverage_class"].strip()
                target_entity_id = rule["target_entity_id"].strip()
                target_entity_cn = rule["target_entity_cn"].strip()
                mapping_relation = rule["mapping_relation"].strip()
                pilot_usable = rule["pilot_usable"].strip().lower()
                rationale = rule["rationale"].strip()

            class_counts[coverage_class] += count
            field_class_counts[field][coverage_class] += count

            if pilot_usable == "yes":
                pilot_usable_counts["yes"] += count
            else:
                pilot_usable_counts["no"] += count

            detail_rows.append(
                {
                    "source_field": field,
                    "source_value": value,
                    "record_count": count,
                    "coverage_class": coverage_class,
                    "target_entity_id": target_entity_id,
                    "target_entity_cn": target_entity_cn,
                    "mapping_relation": mapping_relation,
                    "pilot_usable": pilot_usable,
                    "rationale": rationale,
                }
            )

    total_opportunities = len(metadata) * len(CORE_FIELDS)

    exact_count = class_counts["EXACT"]
    partial_count = class_counts["PARTIAL"]
    unmapped_count = class_counts["UNMAPPED"]
    missing_rule_count = class_counts["MISSING_MAPPING_RULE"]

    summary = {
        "dataset": "PAD-UFES-20",
        "metadata_rows": len(metadata),
        "audited_fields": CORE_FIELDS,
        "audited_field_count": len(CORE_FIELDS),
        "record_field_opportunities": total_opportunities,
        "coverage_definition": (
            "Concept-level mapping coverage for each case-field pair. "
            "This does not yet imply that positive, negative, and unknown "
            "evidence polarity is representable inside the KG."
        ),
        "class_counts": dict(class_counts),
        "strict_exact_rate": safe_rate(
            exact_count,
            total_opportunities,
        ),
        "relaxed_exact_plus_partial_rate": safe_rate(
            exact_count + partial_count,
            total_opportunities,
        ),
        "unmapped_rate": safe_rate(
            unmapped_count,
            total_opportunities,
        ),
        "missing_mapping_rule_rate": safe_rate(
            missing_rule_count,
            total_opportunities,
        ),
        "pilot_usable_rate": safe_rate(
            pilot_usable_counts["yes"],
            total_opportunities,
        ),
        "field_class_counts": {
            field: dict(counts)
            for field, counts in field_class_counts.items()
        },
        "field_value_counts": {
            field: dict(counts)
            for field, counts in field_value_counts.items()
        },
        "important_limitation": (
            "True/False/UNK states are counted separately in value "
            "distributions, but this audit only tests whether the underlying "
            "clinical concept has an acceptable KG mapping. Polarity/state "
            "representation must be audited separately before the Pilot."
        ),
    }

    detail_path = OUTPUT_DIR / "pad_ufes_20_coverage_detail_v1.csv"

    with detail_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "source_field",
                "source_value",
                "record_count",
                "coverage_class",
                "target_entity_id",
                "target_entity_cn",
                "mapping_relation",
                "pilot_usable",
                "rationale",
            ],
        )
        writer.writeheader()
        writer.writerows(detail_rows)

    summary_path = OUTPUT_DIR / "pad_ufes_20_coverage_summary_v1.json"

    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(
            summary,
            f,
            ensure_ascii=False,
            indent=2,
        )

    print("=== PAD-UFES-20 KG Coverage Audit V1 ===")
    print(f"metadata rows: {len(metadata)}")
    print(f"audited fields: {len(CORE_FIELDS)}")
    print(f"record-field opportunities: {total_opportunities}")
    print()

    print("Coverage classes:")
    for key in [
        "EXACT",
        "PARTIAL",
        "UNMAPPED",
        "MISSING_MAPPING_RULE",
    ]:
        count = class_counts[key]
        rate = safe_rate(count, total_opportunities)
        print(f"  {key}: {count} ({rate:.2%})")

    print()
    print(
        "strict EXACT coverage:",
        f"{summary['strict_exact_rate']:.2%}",
    )
    print(
        "relaxed EXACT+PARTIAL coverage:",
        f"{summary['relaxed_exact_plus_partial_rate']:.2%}",
    )
    print(
        "pilot-usable coverage:",
        f"{summary['pilot_usable_rate']:.2%}",
    )

    print()
    print("Field value distributions:")
    for field in CORE_FIELDS:
        print(f"  {field}: {dict(field_value_counts[field])}")

    print()
    print(f"detail output: {detail_path}")
    print(f"summary output: {summary_path}")


if __name__ == "__main__":
    main()