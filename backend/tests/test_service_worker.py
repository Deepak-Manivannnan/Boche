"""The prototype's service worker caches every GET. API responses must never be cached."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from app.main import FRONTEND_DIR

HARNESS = Path(__file__).with_name("sw_harness.js")


def run_service_worker() -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    out = subprocess.run([node, HARNESS, FRONTEND_DIR / "sw.js"], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_service_worker_does_not_answer_api_requests():
    handled = run_service_worker()["handled"]
    assert handled["GET /api/me"] is False
    assert handled["GET /api/public/days/2026-11-10/result.json"] is False


def test_service_worker_still_caches_the_app_shell():
    handled = run_service_worker()["handled"]
    assert handled["GET /app.js"] is True
    assert handled["GET /"] is True


def test_service_worker_cache_name_was_bumped_so_old_caches_are_dropped():
    assert run_service_worker()["cacheName"] != "bocheclub-v130"
