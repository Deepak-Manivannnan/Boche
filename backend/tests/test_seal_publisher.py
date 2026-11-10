"""The GitHub seal publisher: create the file once; never overwrite a different Seal. HTTP is faked."""

import base64
import json

import pytest

from app.seals import GitHubSealPublisher, SealConflict

SEAL = b'{"draw_day": "2026-11-10"}\n'


class FakeGitHub:
    def __init__(self, existing: bytes | None = None):
        self.existing = existing
        self.puts = []

    def __call__(self, method, url, headers, body=None):
        assert headers["Authorization"] == "Bearer tok"
        assert url == "https://api.github.com/repos/acme/seals/contents/seals/2026-11-10.json"
        if method == "GET":
            if self.existing is None:
                return 404, {}
            return 200, {
                "content": base64.b64encode(self.existing).decode(),
                "sha": "blob1",
                "html_url": "https://github.com/acme/seals/blob/main/seals/2026-11-10.json",
            }
        self.puts.append(json.loads(body))
        return 201, {
            "commit": {"sha": "c0ffee"},
            "content": {"html_url": "https://github.com/acme/seals/blob/main/seals/2026-11-10.json"},
        }


def publisher(fake):
    return GitHubSealPublisher("acme/seals", "tok", http=fake)


def test_a_new_seal_is_committed_to_main():
    fake = FakeGitHub()
    sha, url = publisher(fake).publish("2026-11-10", SEAL)
    assert (sha, url) == ("c0ffee", "https://github.com/acme/seals/blob/main/seals/2026-11-10.json")
    put = fake.puts[0]
    assert base64.b64decode(put["content"]) == SEAL
    assert put["branch"] == "main"
    assert "sha" not in put  # creating, never updating


def test_an_identical_seal_already_on_github_is_not_committed_again():
    fake = FakeGitHub(existing=SEAL)
    publisher(fake).publish("2026-11-10", SEAL)
    assert fake.puts == []


def test_a_different_seal_already_on_github_is_never_overwritten():
    fake = FakeGitHub(existing=b'{"draw_day": "2026-11-10", "tampered": true}\n')
    with pytest.raises(SealConflict):
        publisher(fake).publish("2026-11-10", SEAL)
    assert fake.puts == []
