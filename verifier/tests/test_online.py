"""Online mode: Boche site + GitHub seal history + drand relays. HTTP is faked except in the network test."""

import json
import subprocess
import sys
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from drawfiles import CHAIN, DAY, DrawFiles

import verify

SITE = "https://boche.example"
REPO = "acme/boche-draw-seals"


def fake_web(monkeypatch, draw: DrawFiles, commits: list[str], relays_answering: int = 3):
    pages = {
        f"{SITE}/api/public/days/{DAY}/tickets.csv": draw.csv,
        f"{SITE}/api/public/days/{DAY}/result.json": json.dumps(draw.result).encode(),
        f"https://raw.githubusercontent.com/{REPO}/main/seals/{DAY}.json": json.dumps(draw.seal).encode(),
        f"https://api.github.com/repos/{REPO}/commits?path=seals/{DAY}.json&per_page=100": json.dumps(
            [{"commit": {"committer": {"date": d}}} for d in commits]
        ).encode(),
    }
    for base in verify.DRAND_RELAYS[:relays_answering]:
        pages[f"{base}/{CHAIN}/public/{draw.seal['drand']['round']}"] = json.dumps(draw.drand).encode()

    def get(url):
        if url not in pages:
            raise verify.SourceError(f"could not download {url}: 404")
        return pages[url]

    monkeypatch.setattr(verify, "http_get", get)


def run_live(draw):
    return verify.verify(DAY, verify.LiveSources(SITE, REPO))


def status(report, name):
    return report.status(name)


def test_a_genuine_draw_passes_online_with_the_seal_committed_once_at_eight_pm(monkeypatch, draw):
    fake_web(monkeypatch, draw, commits=["2026-11-10T14:30:04Z"])
    report = run_live(draw)
    assert report.ok, report.render()
    assert all(c.status == "PASS" for c in report.checks)


def test_a_seal_that_was_edited_after_it_was_first_committed_fails(monkeypatch, draw):
    fake_web(monkeypatch, draw, commits=["2026-11-10T14:30:04Z", "2026-11-10T15:10:00Z"])
    assert status(run_live(draw), verify.SEAL_PROVENANCE) == "FAIL"


def test_a_seal_first_committed_after_the_randomness_was_released_fails(monkeypatch, draw):
    fake_web(monkeypatch, draw, commits=["2026-11-10T14:50:00Z"])
    assert status(run_live(draw), verify.SEAL_PROVENANCE) == "FAIL"


def test_randomness_confirmed_by_only_one_relay_is_not_enough_online(monkeypatch, draw):
    fake_web(monkeypatch, draw, commits=["2026-11-10T14:30:04Z"], relays_answering=1)
    assert status(run_live(draw), verify.RANDOMNESS) == "FAIL"


def test_a_site_that_cannot_be_reached_is_reported_not_crashed(monkeypatch, draw):
    fake_web(monkeypatch, draw, commits=[])
    report = verify.verify(DAY, verify.LiveSources("https://elsewhere.example", REPO))
    assert report.status(verify.FILES) == "FAIL"
    assert not report.ok


def test_command_line_exits_zero_for_a_genuine_draw_and_one_for_a_tampered_one(draw):
    script = Path(verify.__file__)
    ok = subprocess.run(
        [sys.executable, script, DAY, "--from-dir", draw.folder], capture_output=True, text=True
    )
    assert ok.returncode == 0, ok.stdout
    assert "RESULT: VERIFIED" in ok.stdout

    draw.csv = draw.csv.replace(b"AB 000007", b"ZZ 000007")
    draw.save()
    bad = subprocess.run(
        [sys.executable, script, DAY, "--from-dir", draw.folder], capture_output=True, text=True
    )
    assert bad.returncode == 1
    assert "RESULT: NOT VERIFIED. First failure: Ticket list matches the Seal" in bad.stdout


@pytest.mark.network
def test_live_drand_relays_confirm_a_real_round(tmp_path):
    """Uses the real drand network: a draw sealed one minute before a real, already released round."""
    try:
        urllib.request.urlopen("https://api.drand.sh/health", timeout=5)
    except Exception:
        pytest.skip("no internet access to drand")
    now = datetime.now(UTC)
    round_no = (int(now.timestamp()) - verify.DRAND_GENESIS) // verify.DRAND_PERIOD - 20
    real = dict(verify.drand_from_relays(round_no, verify.DRAND_RELAYS[:1])[0][1])
    files = DrawFiles(tmp_path)
    tickets = [r.split(",", 1)[1] for r in files.csv.decode().splitlines()[1:]]
    ours = verify.pick_winners(tickets, real["randomness"], DAY)
    files.seal["drand"]["round"] = round_no
    files.seal["sealed_at"] = (verify.round_time(round_no) - timedelta(minutes=1)).isoformat()
    files.result["drand"] = {
        "chain_hash": CHAIN,
        **{k: real[k] for k in ("round", "randomness", "signature")},
    }
    files.result["seed"] = ours["seed"]
    files.result["winners"] = ours["winners"]
    files.save()
    (tmp_path / "drand.json").unlink()  # force fetching from the real relays

    report = verify.verify(DAY, verify.FolderSources(tmp_path))
    assert report.status(verify.RANDOMNESS) == "PASS", report.render()
    assert report.status(verify.WINNERS) == "PASS", report.render()
    assert report.ok, report.render()
