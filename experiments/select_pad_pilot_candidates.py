import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "external" / "pad_ufes_20" / "metadata.csv"
OUTPUT = ROOT / "experiments" / "results" / "pad_pilot_candidates_v1.csv"

TARGET_DISEASES = {"BCC", "MEL", "NEV"}

# 当前 KG 最容易利用的病例事实
POSITIVE_FIELDS = ["itch", "bleed", "grew"]

# 当前 KG 部位可直接/安全使用
USABLE_REGIONS = {
    "FACE",
    "BACK",
    "NOSE",
    "CHEST",
    "ABDOMEN",
    "THIGH",
    "FOOT",
}


def main():
    with INPUT.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    # 同一 patient + lesion 只保留一个母病例
    unique_cases = {}
    for row in rows:
        key = (row["patient_id"], row["lesion_id"])
        if key not in unique_cases:
            unique_cases[key] = row

    candidates = []

    for row in unique_cases.values():
        disease = row["diagnostic"].strip()

        if disease not in TARGET_DISEASES:
            continue

        region = row["region"].strip().upper()

        positive_evidence = [
            field
            for field in POSITIVE_FIELDS
            if row[field].strip() == "True"
        ]

        score = len(positive_evidence)

        if region in USABLE_REGIONS:
            score += 1

        # 至少有两个当前 KG 较容易利用的事实
        if score < 2:
            continue

        candidates.append(
            {
                "patient_id": row["patient_id"],
                "lesion_id": row["lesion_id"],
                "diagnostic": disease,
                "region": region,
                "itch": row["itch"],
                "grew": row["grew"],
                "hurt": row["hurt"],
                "changed": row["changed"],
                "bleed": row["bleed"],
                "elevation": row["elevation"],
                "age": row.get("age", ""),
                "gender": row.get("gender", ""),
                "candidate_score": score,
                "positive_evidence": "|".join(positive_evidence),
            }
        )

    candidates.sort(
        key=lambda x: (
            x["diagnostic"],
            -x["candidate_score"],
            x["patient_id"],
        )
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=candidates[0].keys())
        writer.writeheader()
        writer.writerows(candidates)

    print(f"unique patient-lesion cases: {len(unique_cases)}")
    print(f"pilot candidates: {len(candidates)}")

    for disease in sorted(TARGET_DISEASES):
        disease_cases = [x for x in candidates if x["diagnostic"] == disease]
        print(f"{disease}: {len(disease_cases)}")

        for case in disease_cases[:5]:
            print(
                "  ",
                case["patient_id"],
                case["lesion_id"],
                "score=",
                case["candidate_score"],
                "region=",
                case["region"],
                "positive=",
                case["positive_evidence"],
            )

    print(f"\noutput: {OUTPUT}")


if __name__ == "__main__":
    main()