from fastapi.testclient import TestClient

from golden_hour.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_index_served():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Golden Hour" in resp.text
