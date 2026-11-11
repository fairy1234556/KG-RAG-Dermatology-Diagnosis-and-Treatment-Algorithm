"""PAD 运行入口共用的患者输入：先干预原始字段，再生成观察文本。"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from rag.kg_rag_pipeline import PAD_OBSERVATION_FIELDS, format_pad_observation


DEFAULT_CASE_FILE = (
    Path(__file__).resolve().parents[1]
    / "experiments/cases/pad_pilot_mother_cases_v1.csv"
)


def build_pad_input(
    mother_case_id: str,
    removed_fields: Iterable[str] = (),
    case_file: Path = DEFAULT_CASE_FILE,
) -> dict[str, object]:
    """读取冻结的原始字段，返回可直接传给 KGRAGPipeline.run 的输入。

    不读取手写观察或旧结果；每次新建快照，干预不会修改母病例。
    """
    removed = set(removed_fields)
    if removed - set(PAD_OBSERVATION_FIELDS):
        raise ValueError(f"不支持的 PAD 干预字段：{sorted(removed)}")
    with case_file.open(encoding="utf-8-sig", newline="") as stream:
        rows = [row for row in csv.DictReader(stream) if row["mother_case_id"] == mother_case_id]
    if len(rows) != 1:
        raise ValueError(f"PAD 母病例必须唯一：{mother_case_id}，实际 {len(rows)} 条")
    fields = {
        field: rows[0][field]
        for field in PAD_OBSERVATION_FIELDS
        if field not in removed
    }
    return {
        "user_observation": format_pad_observation(fields),
        "structured_fields": fields,
    }
