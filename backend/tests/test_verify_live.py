"""Ticket 11: outsiders can check a Draw day against the live site. The Verifier runs in online mode against
the API (real HTTP routes through the test client); GitHub and drand are faked."""

import json
from datetime import datetime

import pytest
from draw_support import DAY, drand_value, draw, sealed_day
from test_close_and_seal import FakeSeals

import verify
from app.main import REPO_ROOT

SITE = "https://boche.example"
REPO = "acme/boche-draw-seals"


@pytest.fixture
def w(make_client):
    world = sealed_day(make_client)  # sealed with no GitHub publisher configured
    world.seals = FakeSeals()
    world.state.seal_publisher = world.seals
    world.arun.post("/api/tick")  # publishes the pending Seal
    assert DAY in world.seals.files
    return world


def wire(monkeypatch, w, commits=None):
    """Route the Verifier's downloads: site -> the API, GitHub -> fake seals repo, drand -> fake relays."""
    seal = json.loads(w.seals.files[DAY])
    commits = commits or [seal["sealed_at"]]

    def get(url):
        if url.startswith(SITE):
            res = w.arun.get(url[len(SITE) :])
            if res.status_code != 200:
                raise verify.SourceError(f"could not download {url}: {res.status_code}")
            return res.content
        if url == f"https://raw.githubusercontent.com/{REPO}/main/seals/{DAY}.json":
            return w.seals.files[DAY]
        if url == f"https://api.github.com/repos/{REPO}/commits?path=seals/{DAY}.json&per_page=100":
            return json.dumps([{"commit": {"committer": {"date": d}}} for d in commits]).encode()
        if "/public/" in url and url.split("/")[-1].isdigit():
            return json.dumps(drand_value(int(url.split("/")[-1]))).encode()
        raise verify.SourceError(f"unexpected download {url}")

    monkeypatch.setattr(verify, "http_get", get)


def test_the_verifier_confirms_a_published_day_from_the_live_site(w, monkeypatch):
    draw(w, 20, 40)
    wire(monkeypatch, w)
    report = verify.verify(DAY, verify.LiveSources(SITE, REPO))
    assert report.ok, report.render()
    assert all(c.status == "PASS" for c in report.checks), report.render()


def test_the_verifier_catches_a_seal_rewritten_on_github(w, monkeypatch):
    draw(w, 20, 40)
    seal_time = json.loads(w.seals.files[DAY])["sealed_at"]
    wire(monkeypatch, w, commits=[seal_time, datetime(2026, 11, 10, 15, 30).isoformat() + "Z"])
    report = verify.verify(DAY, verify.LiveSources(SITE, REPO))
    assert report.status(verify.SEAL_PROVENANCE) == "FAIL"


def test_before_publish_the_verifier_reports_the_result_as_missing(w, monkeypatch):
    draw(w)  # drawn at 8:16 PM, published only at 8:30 PM
    wire(monkeypatch, w)
    report = verify.verify(DAY, verify.LiveSources(SITE, REPO))
    assert not report.ok and report.status(verify.FILES) == "FAIL"


def test_the_site_serves_the_verifier_unchanged(w):
    res = w.arun.get("/api/public/verifier/verify.py")
    assert res.status_code == 200
    assert res.content == (REPO_ROOT / "verifier" / "verify.py").read_bytes()
    assert "attachment" in res.headers["content-disposition"]


def test_the_verifier_defaults_to_the_hosted_site_and_the_real_seals_repo():
    assert verify.DEFAULT_SITE == "https://boche.onrender.com"
    assert verify.DEFAULT_SEALS_REPO == "Deepak-Manivannnan/boche-draw-seals"
