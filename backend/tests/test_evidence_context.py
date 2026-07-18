from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.evidence_context_service import EvidenceContextService


def test_evidence_context_contains_structured_data_and_markdown():
    context = EvidenceContextService().build("基底细胞癌")
    assert context.structured_context["candidate_disease"]["entity_id"] == "DIS_003"
    assert "主要皮损表现" in context.evidence_sections
    assert "## 主要皮损表现" in context.markdown_context
    assert "珍珠样结节" in context.markdown_context
    assert context.sources


def test_evidence_context_api():
    client = TestClient(app)
    response = client.post(
        "/api/kg-rag/evidence-context",
        json={"candidate_disease": "基底细胞癌"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["structured_context"]["candidate_disease"]["entity_id"] == "DIS_003"
    assert "markdown_context" in data
    assert "evidence_sections" in data

