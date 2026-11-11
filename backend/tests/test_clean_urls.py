"""Clean URLs: app routes such as /draw return the app; API and file paths keep real 404s. The staff page
signs in Admins only: anyone else gets 403 and no account or session."""

import sqlalchemy as sa

from app.db import models as m


def test_app_routes_return_the_app(make_client):
    client = make_client(None)
    for path in ("/", "/draw", "/staff", "/verify-draw/2026-11-10", "/scratch/abc123"):
        res = client.get(path)
        assert res.status_code == 200, path
        assert '<main class="screen" id="screen">' in res.text, path


def test_files_and_api_paths_still_404(make_client):
    client = make_client(None)
    assert client.get("/missing.js").status_code == 404
    assert client.get("/api/no-such-thing").status_code == 404
    assert client.get("/app.js").status_code == 200


def test_assets_load_from_the_root_on_nested_routes(make_client):
    html = make_client(None).get("/verify-draw/2026-11-10").text
    assert 'src="/app.js"' in html and 'href="/app.css"' in html


def test_the_staff_page_refuses_a_non_admin_without_signing_them_in(make_client, db_engine):
    client = make_client(None)
    res = client.post("/api/auth/google", json={"credential": "stranger-token-xxxxxxxxxx", "admin": True})
    assert res.status_code == 403
    assert "not a Lucky Draw admin" in res.json()["detail"]
    assert client.get("/api/me").status_code == 401
    with db_engine.connect() as conn:
        assert conn.scalar(sa.select(sa.func.count()).select_from(m.User)) == 0


def test_the_staff_page_signs_in_an_admin(make_client):
    client = make_client(None)
    res = client.post("/api/auth/google", json={"credential": "admin-token-xxxxxxxxxx", "admin": True})
    assert res.status_code == 200 and res.json()["role"] == "admin"
