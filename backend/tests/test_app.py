from fastapi.testclient import TestClient

from app.main import create_app


def client() -> TestClient:
    return TestClient(create_app())


def test_health_endpoint_reports_ok():
    res = client().get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_root_serves_the_prototype_index_page():
    res = client().get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "<title>Boche</title>" in res.text


def test_prototype_assets_are_served_unchanged():
    from app.main import FRONTEND_DIR

    res = client().get("/data.js")
    assert res.status_code == 200
    assert res.content == (FRONTEND_DIR / "data.js").read_bytes()


def test_unknown_api_path_is_404_not_the_frontend():
    res = client().get("/api/does-not-exist")
    assert res.status_code == 404
