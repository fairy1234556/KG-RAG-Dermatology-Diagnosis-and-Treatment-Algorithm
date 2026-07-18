from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app


def test_health_check():
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["service_status"] == "ok"
    assert body["data"]["system_version"] == "v1.0-stage1"
    assert body["data"]["kg_loaded"] is True

