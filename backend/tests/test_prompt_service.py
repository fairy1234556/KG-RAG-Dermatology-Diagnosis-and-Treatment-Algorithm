from __future__ import annotations

import json

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.prompt_service import PromptService
from backend.app.services.template_generation_service import TemplateGenerationService


def test_prompt_contains_disease_observation_evidence_and_safety():
    prompt = PromptService().build_prompt(
        candidate_disease="基底细胞癌",
        user_observation="患者皮损表现为珍珠样结节，表面可见血管，位于面部。",
    )
    assert "基底细胞癌" in prompt.prompt_text
    assert "珍珠样结节" in prompt.prompt_text
    assert "知识图谱证据上下文" in prompt.prompt_text
    assert "不得输出处方、药物剂量" in prompt.prompt_text
    assert "不得输出患病概率" in prompt.prompt_text


def test_template_generation_uses_graph_evidence_and_safe_language():
    result = TemplateGenerationService().generate(
        candidate_disease="基底细胞癌",
        user_observation="患者皮损表现为珍珠样结节，表面可见血管，位于面部。",
    )
    text = json.dumps(result.model_dump(), ensure_ascii=False)
    assert result.generation_mode == "template"
    assert "珍珠样结节" in text
    assert "仅用于辅助决策，不替代医生诊断" in text
    assert "处方" not in text
    assert "剂量" not in text
    assert "患病概率" not in text
    forbidden_diagnosis_phrases = [
        "已确诊",
        "已经确诊",
        "确诊为",
        "患者确诊",
        "系统确诊",
        "可以确定患有",
        "最终诊断为",
    ]
    assert not any(phrase in text for phrase in forbidden_diagnosis_phrases)


def test_prompt_api_and_template_api():
    client = TestClient(app)
    prompt_response = client.post(
        "/api/kg-rag/prompts",
        json={
            "candidate_disease": "基底细胞癌",
            "user_observation": "患者皮损表现为珍珠样结节，表面可见血管，位于面部。",
        },
    )
    assert prompt_response.status_code == 200
    assert "prompt_text" in prompt_response.json()["data"]

    template_response = client.post(
        "/api/kg-rag/template-generations",
        json={
            "candidate_disease": "基底细胞癌",
            "user_observation": "患者皮损表现为珍珠样结节，表面可见血管，位于面部。",
        },
    )
    assert template_response.status_code == 200
    data = template_response.json()["data"]
    assert data["generation_mode"] == "template"
    assert data["candidate_disease"] == "基底细胞癌"


def test_analysis_runs_placeholder_does_not_fake_results():
    client = TestClient(app)
    response = client.post("/api/cases/CASE_001/analysis-runs")
    assert response.status_code == 501
    body = response.json()
    assert body["success"] is False
    assert body["data"]["error_code"] == "NOT_IMPLEMENTED"
