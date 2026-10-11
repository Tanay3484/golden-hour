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


def test_static_assets_served_with_js_mime():
    resp = client.get("/static/app.js")
    assert resp.status_code == 200
    assert "javascript" in resp.headers["content-type"]
    assert client.get("/static/style.css").status_code == 200


def test_frontend_is_revalidated_after_deploys():
    for path in ("/", "/static/app.js", "/static/time.js", "/static/style.css"):
        assert client.get(path).headers["cache-control"] == "no-cache", path
    assert "cache-control" not in client.get("/api/health").headers


def test_unchanged_static_file_returns_304():
    first = client.get("/static/app.js")
    again = client.get("/static/app.js", headers={"If-None-Match": first.headers["etag"]})
    assert again.status_code == 304
