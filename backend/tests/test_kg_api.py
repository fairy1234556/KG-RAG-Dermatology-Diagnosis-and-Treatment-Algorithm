from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app


def test_kg_status_api():
    client = TestClient(app)
    response = client.get("/api/kg/status")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["entity_count"] == 70
    assert data["triple_count"] == 102
    assert data["source_count"] == 25
    assert data["disease_count"] == 7


def test_diseases_api_returns_ham10000_labels():
    client = TestClient(app)
    response = client.get("/api/kg/diseases")
    assert response.status_code == 200
    diseases = response.json()["data"]
    labels = {item["ham10000_label"] for item in diseases}
    assert labels == {"mel", "nv", "bcc", "akiec", "bkl", "df", "vasc"}


def test_disease_evidence_api():
    client = TestClient(app)
    response = client.get("/api/kg/diseases/DIS_003/evidence")
    assert response.status_code == 200
    evidence = response.json()["data"]
    assert any(item["triple_id"] == "TRI_025" for item in evidence)
    assert evidence[0]["head"]["entity_id"] == "DIS_003"


def test_feature_reverse_lookup_api():
    client = TestClient(app)
    response = client.get("/api/kg/features/珍珠样结节/diseases")
    assert response.status_code == 200
    matches = response.json()["data"]
    assert any(match["disease"]["entity_id"] == "DIS_003" for match in matches)


def test_unknown_disease_api_error():
    client = TestClient(app)
    response = client.get("/api/kg/diseases/UNKNOWN/evidence")
    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["data"]["error_code"] == "KG_DISEASE_NOT_FOUND"

