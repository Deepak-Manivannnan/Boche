"""Publishing each Draw day's Seal to the public GitHub seals repository (ADR-0003).

A Seal is committed once and never edited: if a file for that day already exists with the same bytes,
nothing is done; if it exists with different bytes, publishing stops with SealConflict. The Verifier
treats more than one commit of a Seal file as tampering."""

import base64
import json
from collections.abc import Callable

import requests

API = "https://api.github.com"


class SealConflict(Exception):
    """GitHub already holds a different Seal for this Draw day."""


def _http(method: str, url: str, headers: dict, body: str | None = None) -> tuple[int, dict]:
    res = requests.request(method, url, headers=headers, data=body, timeout=20)
    try:
        data = res.json()
    except ValueError:
        data = {}
    return res.status_code, data


class GitHubSealPublisher:
    def __init__(self, repo: str, token: str, http: Callable = _http, branch: str = "main"):
        self.repo, self.branch, self._http = repo, branch, http
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "boche-lucky-draw",
        }

    def exists(self, label: str) -> bool:
        """Whether seals/<label>.json is already in the repository."""
        status, _ = self._http("GET", f"{API}/repos/{self.repo}/contents/seals/{label}.json", self._headers)
        if status not in (200, 404):
            raise OSError(f"GitHub answered {status} when checking the Seal for {label}")
        return status == 200

    def publish(self, label: str, content: bytes) -> tuple[str | None, str]:
        """Commit seals/<label>.json. Returns (commit sha, or None if it was already there; file URL)."""
        url = f"{API}/repos/{self.repo}/contents/seals/{label}.json"
        status, existing = self._http("GET", url, self._headers)
        if status == 200:
            if base64.b64decode(existing.get("content", "")) != content:
                raise SealConflict(f"a different Seal for {label} is already on GitHub")
            return None, existing.get("html_url", "")
        if status != 404:
            raise OSError(f"GitHub answered {status} when reading the Seal for {label}")

        body = json.dumps(
            {
                "message": f"Seal for Draw day {label}",
                "content": base64.b64encode(content).decode(),
                "branch": self.branch,
            }
        )
        status, created = self._http("PUT", url, self._headers, body)
        if status not in (200, 201):
            raise OSError(f"GitHub answered {status} when committing the Seal for {label}")
        return created["commit"]["sha"], created["content"]["html_url"]
