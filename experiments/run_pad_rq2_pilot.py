from __future__ import annotations

import csv
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from kg.path_ranker import EvidencePathRanker
from kg.path_retriever import GraphPathRetriever
from rag.kg_rag_pipeline import KGRAGPipeline


ORIGINAL_TRIPLE_FILE = (
    ROOT / "kg" / "csv" / "triples.csv"
)

OUTPUT_PATH = (
    ROOT
    / "experiments"
    / "results"
    / "rq2_pilot_v1"
    / "pad_bcc_001_kg_intervention.json"
)


OBSERVATION = (
    "74岁女性，面部皮损，"
    "伴瘙痒、增长、触痛、出血及隆起。"
)

CANDIDATE_DISEASE = "基底细胞癌"


CONDITIONS = [
    {
        "condition_id": "PAD_BCC_001_K0",
        "kg_condition": "original_kg",
        "removed_triples": [],
    },
    {
        "condition_id": "PAD_BCC_001_K1",
        "kg_condition": "remove_bleeding_support",
        "removed_triples": ["TRI_031"],
    },
    {
        "condition_id": "PAD_BCC_001_K2",
        "kg_condition": "remove_bleeding_and_site_support",
        "removed_triples": ["TRI_030", "TRI_031"],
    },
        {
        "condition_id": "PAD_BCC_001_K3",
        "kg_condition": "remove_direct_support_and_bleeding_alternative",
        "removed_triples": [
            "TRI_030",
            "TRI_031",
            "TRI_035",
        ],
    },
]


def result_to_dict(result):
    if hasattr(result, "model_dump"):
        return result.model_dump()

    return result.dict()


def build_intervened_triple_file(
    output_path: Path,
    removed_triples: set[str],
):
    with ORIGINAL_TRIPLE_FILE.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        reader = csv.DictReader(f)

        fieldnames = reader.fieldnames

        rows = [
            row
            for row in reader
            if row["triple_id"] not in removed_triples
        ]

    with output_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(rows)


def build_pipeline(
    triple_file: Path,
):
    ranker = EvidencePathRanker()

    ranker.path_retriever = GraphPathRetriever(
        triple_file=triple_file
    )

    return KGRAGPipeline(
        ranker=ranker
    )


def main():
    all_results = []

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir = Path(temp_dir)

        for condition in CONDITIONS:
            removed_triples = set(
                condition["removed_triples"]
            )

            if removed_triples:
                triple_file = (
                    temp_dir
                    / f"{condition['condition_id']}_triples.csv"
                )

                build_intervened_triple_file(
                    output_path=triple_file,
                    removed_triples=removed_triples,
                )
            else:
                triple_file = ORIGINAL_TRIPLE_FILE

            pipeline = build_pipeline(
                triple_file=triple_file
            )

            print()
            print("=" * 70)
            print(condition["condition_id"])
            print(
                "removed_triples:",
                condition["removed_triples"],
            )
            print(
                "observation:",
                OBSERVATION,
            )

            result = pipeline.run(
                case_id=condition["condition_id"],
                candidate_disease=CANDIDATE_DISEASE,
                user_observation=OBSERVATION,
                top_k=5,
                max_hops=2,
            )

            data = result_to_dict(result)

            data["kg_condition"] = (
                condition["kg_condition"]
            )
            data["removed_triples"] = (
                condition["removed_triples"]
            )

            all_results.append(data)

            print(
                "run_status:",
                data.get("run_status"),
            )

            print("evidence_paths:")

            for index, path in enumerate(
                data.get("evidence_paths", []),
                start=1,
            ):
                print(
                    f"  path {index}:",
                    path.get("head_entity"),
                    "->",
                    path.get("relation"),
                    "->",
                    path.get("tail_entity"),
                    "source_id=",
                    path.get("source_id"),
                )

            print("observation_match:")

            for item in data.get(
                "observation_match",
                [],
            ):
                print("  -", item)

            print("supporting_evidence:")

            for item in data.get(
                "supporting_evidence",
                [],
            ):
                print("  -", item)

            print("evidence_gap:")

            for item in data.get(
                "evidence_gap",
                [],
            ):
                print("  -", item)

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            all_results,
            f,
            ensure_ascii=False,
            indent=2,
        )

    print()
    print("=" * 70)
    print("RQ2 Pilot finished.")
    print("output:", OUTPUT_PATH)


if __name__ == "__main__":
    main()