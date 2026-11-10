from fastapi.testclient import TestClient

from app.main import FRONTEND_DIR, create_app

UNREACHABLE_DB = "mysql+pymysql://nobody:wrong@127.0.0.1:1/none?connect_timeout=1"


def client(database_url: str = UNREACHABLE_DB) -> TestClient:
    return TestClient(create_app(database_url=database_url))


def test_health_reports_ok_and_a_connected_database(migrated_url):
    res = client(migrated_url).get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "database": "connected"}


def test_health_reports_503_when_the_database_is_unreachable():
    res = client().get("/api/health")
    assert res.status_code == 503
    assert res.json() == {"status": "degraded", "database": "unreachable"}


def test_root_serves_the_prototype_index_page():
    res = client().get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "<title>Boche</title>" in res.text


def test_prototype_assets_are_served_unchanged():
    res = client().get("/data.js")
    assert res.status_code == 200
    assert res.content == (FRONTEND_DIR / "data.js").read_bytes()


def test_unknown_api_path_is_404_not_the_frontend():
    res = client().get("/api/does-not-exist")
    assert res.status_code == 404
