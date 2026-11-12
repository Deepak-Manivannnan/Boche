"""The GitHub seal publisher: create the file once; never overwrite a different Seal. HTTP is faked."""

import base64
import json

import pytest

from app.draw.seals import GitHubSealPublisher, SealConflict

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


class FakeGitHubWithDelete(FakeGitHub):
    def __init__(self, existing=None, delete_status=200):
        super().__init__(existing)
        self.deletes, self.delete_status = [], delete_status

    def __call__(self, method, url, headers, body=None):
        if method == "DELETE":
            self.deletes.append(json.loads(body))
            return self.delete_status, {}
        return super().__call__(method, url, headers, body)


def test_deleting_a_seal_removes_that_file_on_main():
    fake = FakeGitHubWithDelete(existing=SEAL)
    assert publisher(fake).delete("2026-11-10") is True
    assert fake.deletes[0]["sha"] == "blob1" and fake.deletes[0]["branch"] == "main"


def test_deleting_a_missing_seal_does_nothing():
    fake = FakeGitHubWithDelete()
    assert publisher(fake).delete("2026-11-10") is False
    assert fake.deletes == []


def test_a_failed_delete_raises():
    with pytest.raises(OSError):
        publisher(FakeGitHubWithDelete(existing=SEAL, delete_status=409)).delete("2026-11-10")


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
