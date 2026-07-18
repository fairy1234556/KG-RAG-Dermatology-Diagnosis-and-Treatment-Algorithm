from __future__ import annotations

import subprocess
import sys

import pytest

from backend.app.schemas.common import AppError
from backend.app.services.kg_repository import KGRepository


def test_kg_load_counts():
    repo = KGRepository()
    status = repo.status()
    assert status.entity_count == 70
    assert status.triple_count == 102
    assert status.source_count == 25
    assert status.disease_count == 7
    assert status.csv_available is True


def test_disease_lookup_by_chinese_english_id_and_alias():
    repo = KGRepository()
    assert repo.find_disease("基底细胞癌")["id"] == "DIS_003"
    assert repo.find_disease("Basal Cell Carcinoma")["id"] == "DIS_003"
    assert repo.find_disease("DIS_003")["id"] == "DIS_003"
    assert repo.find_disease("bcc")["id"] == "DIS_003"


def test_feature_lookup_by_chinese_english_id_and_alias():
    repo = KGRepository()
    for query in ("珍珠样结节", "Pearly Nodule", "LF_010", "shiny or pearly nodule"):
        matches = repo.diseases_by_feature(query)
        assert any(match.disease.entity_id == "DIS_003" for match in matches)


def test_basal_cell_carcinoma_evidence():
    repo = KGRepository()
    evidence = repo.evidence_by_disease("DIS_003")
    assert len(evidence) > 0
    assert any(item.triple_id == "TRI_025" for item in evidence)
    assert any(item.tail.name_cn == "珍珠样结节" for item in evidence)


def test_unknown_disease_has_clear_error():
    repo = KGRepository()
    with pytest.raises(AppError) as exc:
        repo.evidence_by_disease("不存在的疾病")
    assert exc.value.error_code == "KG_DISEASE_NOT_FOUND"


def test_original_kg_and_rag_demos_still_run(repo_root):
    kg_result = subprocess.run(
        [sys.executable, "kg/kg_query_demo.py"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "基底细胞癌" in kg_result.stdout

    rag_result = subprocess.run(
        [sys.executable, "rag/kg_rag_prompt_demo.py"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    assert rag_result.returncode == 0
    assert "候选疾病" in rag_result.stdout
    assert "知识图谱证据上下文" in rag_result.stdout
    assert "基底细胞癌" in rag_result.stdout
    assert "证据路径" in rag_result.stdout
