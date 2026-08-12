from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from rag.kg_rag_pipeline import KGRAGPipeline


OUTPUT_PATH = (
    ROOT
    / "experiments"
    / "results"
    / "rq1_pilot_v1"
    / "pad_rq1_pilot_4cases.json"
)

CONDITIONS = [
    # ============================================================
    # BCC 001
    # ============================================================
    {
        "condition_id": "PAD_BCC_001_P0",
        "candidate_disease": "基底细胞癌",
        "condition": "original",
        "removed_evidence": [],
        "observation": (
            "74岁女性，面部皮损，"
            "伴瘙痒、增长、触痛、出血及隆起。"
        ),
    },
    {
        "condition_id": "PAD_BCC_001_P1",
        "candidate_disease": "基底细胞癌",
        "condition": "remove_bleeding",
        "removed_evidence": ["bleed"],
        "observation": (
            "74岁女性，面部皮损，"
            "伴瘙痒、增长、触痛及隆起。"
        ),
    },
    {
        "condition_id": "PAD_BCC_001_P2",
        "candidate_disease": "基底细胞癌",
        "condition": "remove_bleeding_and_site",
        "removed_evidence": ["bleed", "region"],
        "observation": (
            "74岁女性，皮损伴瘙痒、增长、触痛及隆起。"
        ),
    },

    # ============================================================
    # BCC 002
    # ============================================================
    {
        "condition_id": "PAD_BCC_002_P0",
        "candidate_disease": "基底细胞癌",
        "condition": "original",
        "removed_evidence": [],
        "observation": (
            "48岁男性，面部皮损，"
            "伴瘙痒、增长及出血。"
        ),
    },
    {
        "condition_id": "PAD_BCC_002_P1",
        "candidate_disease": "基底细胞癌",
        "condition": "remove_bleeding",
        "removed_evidence": ["bleed"],
        "observation": (
            "48岁男性，面部皮损，"
            "伴瘙痒及增长。"
        ),
    },
    {
        "condition_id": "PAD_BCC_002_P2",
        "candidate_disease": "基底细胞癌",
        "condition": "remove_bleeding_and_site",
        "removed_evidence": ["bleed", "region"],
        "observation": (
            "48岁男性，皮损伴瘙痒及增长。"
        ),
    },

    # ============================================================
    # MEL 001
    # ============================================================
    {
        "condition_id": "PAD_MEL_001_P0",
        "candidate_disease": "黑色素瘤",
        "condition": "original",
        "removed_evidence": [],
        "observation": (
            "54岁女性，背部皮损，"
            "伴瘙痒、增长、变化及隆起。"
        ),
    },
    {
        "condition_id": "PAD_MEL_001_P1",
        "candidate_disease": "黑色素瘤",
        "condition": "remove_pruritus",
        "removed_evidence": ["itch"],
        "observation": (
            "54岁女性，背部皮损，"
            "伴增长、变化及隆起。"
        ),
    },
    {
        "condition_id": "PAD_MEL_001_P2",
        "candidate_disease": "黑色素瘤",
        "condition": "remove_pruritus_and_site",
        "removed_evidence": ["itch", "region"],
        "observation": (
            "54岁女性，皮损伴增长、变化及隆起。"
        ),
    },

    # ============================================================
    # MEL 002
    # ============================================================
    {
        "condition_id": "PAD_MEL_002_P0",
        "candidate_disease": "黑色素瘤",
        "condition": "original",
        "removed_evidence": [],
        "observation": (
            "58岁男性，背部皮损，"
            "伴瘙痒、增长及变化。"
        ),
    },
    {
        "condition_id": "PAD_MEL_002_P1",
        "candidate_disease": "黑色素瘤",
        "condition": "remove_pruritus",
        "removed_evidence": ["itch"],
        "observation": (
            "58岁男性，背部皮损，"
            "伴增长及变化。"
        ),
    },
    {
        "condition_id": "PAD_MEL_002_P2",
        "candidate_disease": "黑色素瘤",
        "condition": "remove_pruritus_and_site",
        "removed_evidence": ["itch", "region"],
        "observation": (
            "58岁男性，皮损伴增长及变化。"
        ),
    },
]


def result_to_dict(result):
    if hasattr(result, "model_dump"):
        return result.model_dump()

    return result.dict()


def main():
    pipeline = KGRAGPipeline()

    all_results = []

    for condition in CONDITIONS:
        print()
        print("=" * 70)
        print(condition["condition_id"])
        print("observation:", condition["observation"])

        result = pipeline.run(
             case_id=condition["condition_id"],
             candidate_disease=condition["candidate_disease"],
             user_observation=condition["observation"],
             top_k=5,
             max_hops=2,
        )

        data = result_to_dict(result)

        data["pilot_condition"] = condition["condition"]
        data["removed_evidence"] = condition["removed_evidence"]

        all_results.append(data)

        print("run_status:", data.get("run_status"))

        paths = data.get("evidence_paths", [])

        print("evidence_path_count:", len(paths))

        for index, path in enumerate(paths, start=1):
            print(
                f"  path {index}:",
                path.get("head_entity"),
                "->",
                path.get("relation"),
                "->",
                path.get("tail_entity"),
                "score=",
                path.get("score"),
            )

        print("evidence_gap:", data.get("evidence_gap"))

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
    print("Pilot finished.")
    print("output:", OUTPUT_PATH)


if __name__ == "__main__":
    main()