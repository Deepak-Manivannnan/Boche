"""Builds a genuine Draw day's public files with the real engine, so tests can tamper with them."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from engine import canonical_csv, pick_winners

GENESIS = 1692803367  # drand quicknet
PERIOD = 3
CHAIN = "52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971"
DAY = "2026-11-10"
SEALED_AT = "2026-11-10T14:30:00Z"  # 8:00 PM IST
DRAW_TIME = datetime(2026, 11, 10, 14, 45, tzinfo=UTC)  # 8:15 PM IST


def round_at(t: datetime) -> int:
    return (int(t.timestamp()) - GENESIS + PERIOD - 1) // PERIOD + 1


def drand_response(round_no: int, salt: str = "") -> dict:
    signature = hashlib.sha256(f"sig-{round_no}{salt}".encode()).hexdigest() * 3  # 96 bytes like quicknet
    return {
        "round": round_no,
        "randomness": hashlib.sha256(bytes.fromhex(signature)).hexdigest(),
        "signature": signature,
    }


class DrawFiles:
    """The four public artefacts of one Draw day, written to a folder."""

    def __init__(self, folder: Path, ticket_count: int = 300):
        self.folder = folder
        tickets = [f"AB {i:06d}" for i in range(1, ticket_count + 1)]
        csv = canonical_csv(tickets)
        rnd = round_at(DRAW_TIME)
        drand = drand_response(rnd)
        result = pick_winners(tickets, drand["randomness"], DAY)
        self.csv = csv
        self.drand = drand
        self.seal = {
            "scheme": "boche-draw-v1",
            "draw_day": DAY,
            "kind": "real",
            "ticket_count": ticket_count,
            "fingerprint": result.fingerprint,
            "drand": {"chain_hash": CHAIN, "round": rnd},
            "sealed_at": SEALED_AT,
        }
        self.result = {
            "scheme": "boche-draw-v1",
            "draw_day": DAY,
            "kind": "real",
            "ticket_count": ticket_count,
            "fingerprint": result.fingerprint,
            "seed": result.seed,
            "drand": {"chain_hash": CHAIN, **drand},
            "winners": [
                {"rank": w.rank, "prize": w.prize, "position": w.position, "ticket": w.ticket}
                for w in result.winners
            ],
            "drawn_at": "2026-11-10T14:46:02Z",
            "published_at": "2026-11-10T15:00:00Z",
        }
        self.save()

    def save(self) -> None:
        (self.folder / "tickets.csv").write_bytes(self.csv)
        (self.folder / "seal.json").write_text(json.dumps(self.seal), encoding="utf-8")
        (self.folder / "result.json").write_text(json.dumps(self.result), encoding="utf-8")
        (self.folder / "drand.json").write_text(json.dumps(self.drand), encoding="utf-8")


@pytest.fixture
def draw(tmp_path: Path) -> DrawFiles:
    return DrawFiles(tmp_path)
