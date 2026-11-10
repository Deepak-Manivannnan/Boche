#!/usr/bin/env python3
"""Boche Lucky Draw Verifier.

Checks that a past Draw day's result was not manipulated, without trusting Boche's servers.
Needs only Python 3.11+ (no packages to install).

    python verify.py 2026-11-10                      # check a real Draw day online
    python verify.py 2026-11-10 --from-dir ./day     # check downloaded files offline

It reads three independent sources:
  1. Boche's download page: the Ticket list (tickets.csv) and the result (result.json)
  2. The public GitHub seals repository: the Seal committed when Entries closed
  3. drand's public relays: the Randomness round named in the Seal

and then recomputes the ten Winners with the same published algorithm (boche-draw-v1).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

SCHEME = "boche-draw-v1"
WINNER_COUNT = 10
MAIN_PRIZES = 3
CSV_HEADER = "position,ticket_number"

# drand quicknet, run by the League of Entropy (https://drand.love)
DRAND_CHAIN = "52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971"
DRAND_GENESIS = 1692803367
DRAND_PERIOD = 3
DRAND_RELAYS = [
    "https://api.drand.sh",
    "https://api2.drand.sh",
    "https://api3.drand.sh",
    "https://drand.cloudflare.com",
]

DEFAULT_SITE = "https://boche.onrender.com"
DEFAULT_SEALS_REPO = "Deepak-Manivannnan/boche-draw-seals"

# Check names, in the order they run
FILES = "Public files downloaded"
SEAL = "Seal is for this Draw day"
SEAL_PROVENANCE = "Seal was published on GitHub before the draw and never changed"
TICKET_LIST = "Ticket list matches the Seal"
ROUND_AFTER_SEAL = "Randomness round was still unknown when Entries closed"
RANDOMNESS = "Randomness matches drand"
WINNERS = "Recomputed Winners match the published Winners"


# --------------------------------------------------------------------------------------------
# The draw algorithm. A line-for-line copy of the engine package; tests keep the two identical.
# --------------------------------------------------------------------------------------------


class EngineError(ValueError):
    pass


def canonical_csv(tickets) -> bytes:
    ordered = sorted(tickets)
    for i, ticket in enumerate(ordered):
        if not ticket or any(ch in ticket for ch in ",\n\r"):
            raise EngineError(f"ticket {ticket!r} is empty or contains a comma or line break")
        if i and ordered[i - 1] == ticket:
            raise EngineError(f"duplicate ticket {ticket!r}")
    lines = [CSV_HEADER] + [f"{pos},{ticket}" for pos, ticket in enumerate(ordered, start=1)]
    return ("\n".join(lines) + "\n").encode("utf-8")


def fingerprint(csv_bytes: bytes) -> str:
    return hashlib.sha256(csv_bytes).hexdigest()


def derive_seed(randomness: str, list_fingerprint: str, draw_day: str) -> bytes:
    text = f"{SCHEME}|{randomness}|{list_fingerprint}|{draw_day}"
    return hashlib.sha256(text.encode("ascii")).digest()


def unbiased_index(seed: bytes, pick: int, n: int) -> int:
    limit = (1 << 256) - ((1 << 256) % n)
    attempt = 0
    while True:
        h = int.from_bytes(
            hashlib.sha256(seed + f"|pick:{pick}|try:{attempt}".encode("ascii")).digest(), "big"
        )
        if h < limit:
            return h % n
        attempt += 1


def pick_winners(tickets, randomness: str, draw_day: str, count: int = WINNER_COUNT) -> dict:
    csv = canonical_csv(tickets)
    ordered = [line.split(",", 1)[1] for line in csv.decode("utf-8").splitlines()[1:]]
    if len(ordered) < count:
        raise EngineError(f"a draw needs at least {count} tickets, got {len(ordered)}")
    list_fp = fingerprint(csv)
    seed = derive_seed(randomness, list_fp, draw_day)
    remaining = list(range(1, len(ordered) + 1))
    winners = []
    for rank in range(1, count + 1):
        position = remaining.pop(unbiased_index(seed, rank, len(remaining)))
        prize = "main" if rank <= MAIN_PRIZES else "consolation"
        winners.append({"rank": rank, "prize": prize, "position": position, "ticket": ordered[position - 1]})
    return {"fingerprint": list_fp, "seed": seed.hex(), "winners": winners}


# --------------------------------------------------------------------------------------------
# Where the evidence comes from
# --------------------------------------------------------------------------------------------


class SourceError(Exception):
    pass


@dataclass
class SealRecord:
    seal: dict
    published_at: datetime | None  # when an independent party (GitHub) first recorded it
    revisions: int | None  # how many times it was committed; 1 means never changed
    where: str


def http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "boche-verifier/1", "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            return res.read()
    except (urllib.error.URLError, TimeoutError) as e:
        raise SourceError(f"could not download {url}: {e}") from e


def drand_from_relays(round_no: int, relays: list[str]) -> list[tuple[str, dict]]:
    found = []
    for base in relays:
        try:
            found.append((base, json.loads(http_get(f"{base}/{DRAND_CHAIN}/public/{round_no}"))))
        except (SourceError, ValueError):
            continue
    return found


class LiveSources:
    """Boche's site, the GitHub seals repository and drand relays, over the internet."""

    min_drand_sources = 2

    def __init__(self, site: str, seals_repo: str, relays: list[str] | None = None):
        self.site = site.rstrip("/")
        self.repo = seals_repo
        self.relays = relays or DRAND_RELAYS

    def tickets_csv(self, day: str) -> tuple[bytes, str]:
        url = f"{self.site}/api/public/days/{day}/tickets.csv"
        return http_get(url), url

    def result(self, day: str) -> tuple[dict, str]:
        url = f"{self.site}/api/public/days/{day}/result.json"
        return json.loads(http_get(url)), url

    def seal(self, day: str) -> SealRecord:
        path = f"seals/{day}.json"
        raw = f"https://raw.githubusercontent.com/{self.repo}/main/{path}"
        seal = json.loads(http_get(raw))
        commits = json.loads(
            http_get(f"https://api.github.com/repos/{self.repo}/commits?path={path}&per_page=100")
        )
        first = (
            min(datetime.fromisoformat(c["commit"]["committer"]["date"]) for c in commits)
            if commits
            else None
        )
        return SealRecord(seal, first, len(commits), raw)

    def drand(self, round_no: int) -> list[tuple[str, dict]]:
        return drand_from_relays(round_no, self.relays)


class FolderSources:
    """Files saved in one folder: tickets.csv, result.json, seal.json and optionally drand.json.

    Without drand.json the Randomness round is fetched live from drand's relays. The Seal's
    publication time cannot be checked offline, so that check is reported as a warning.
    """

    min_drand_sources = 1

    def __init__(self, folder: Path | str, relays: list[str] | None = None):
        self.folder = Path(folder)
        self.relays = relays or DRAND_RELAYS

    def _read(self, name: str) -> bytes:
        path = self.folder / name
        if not path.is_file():
            raise SourceError(f"{name} not found in {self.folder}")
        return path.read_bytes()

    def tickets_csv(self, day: str) -> tuple[bytes, str]:
        return self._read("tickets.csv"), str(self.folder / "tickets.csv")

    def result(self, day: str) -> tuple[dict, str]:
        return json.loads(self._read("result.json")), str(self.folder / "result.json")

    def seal(self, day: str) -> SealRecord:
        return SealRecord(json.loads(self._read("seal.json")), None, None, str(self.folder / "seal.json"))

    def drand(self, round_no: int) -> list[tuple[str, dict]]:
        if (self.folder / "drand.json").is_file():
            return [(str(self.folder / "drand.json"), json.loads(self._read("drand.json")))]
        self.min_drand_sources = 2
        return drand_from_relays(round_no, self.relays)


# --------------------------------------------------------------------------------------------
# The checks
# --------------------------------------------------------------------------------------------


@dataclass
class Check:
    name: str
    status: str  # PASS, FAIL, WARN or SKIP
    detail: str


@dataclass
class Report:
    draw_day: str
    checks: list[Check] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.status in ("PASS", "WARN") for c in self.checks)

    def first_failure(self) -> Check | None:
        return next((c for c in self.checks if c.status == "FAIL"), None)

    def status(self, name: str) -> str | None:
        return next((c.status for c in self.checks if c.name == name), None)

    def add(self, name: str, passed: bool, detail: str, *, warn: bool = False) -> bool:
        self.checks.append(Check(name, "WARN" if warn else ("PASS" if passed else "FAIL"), detail))
        return passed

    def skip(self, *names: str) -> None:
        for name in names:
            if all(c.name != name for c in self.checks):
                self.checks.append(Check(name, "SKIP", "not checked because an earlier check failed"))

    def render(self) -> str:
        lines = [f"Boche Lucky Draw Verifier ({SCHEME}) - Draw day {self.draw_day}", ""]
        for c in self.checks:
            lines.append(f"[{c.status}] {c.name}")
            lines.extend(f"       {part}" for part in c.detail.splitlines())
        lines.append("")
        if self.ok:
            lines.append(
                "RESULT: VERIFIED. The published Winners follow from the sealed Ticket list and drand."
            )
        else:
            failed = self.first_failure()
            lines.append(f"RESULT: NOT VERIFIED. First failure: {failed.name if failed else 'incomplete'}")
        return "\n".join(lines)


def round_time(round_no: int) -> datetime:
    return datetime.fromtimestamp(DRAND_GENESIS + (round_no - 1) * DRAND_PERIOD, tz=UTC)


def verify(day: str, sources) -> Report:
    report = Report(day)
    later = [SEAL, SEAL_PROVENANCE, TICKET_LIST, ROUND_AFTER_SEAL, RANDOMNESS, WINNERS]

    try:
        csv_bytes, csv_where = sources.tickets_csv(day)
        result, result_where = sources.result(day)
        record = sources.seal(day)
    except (SourceError, ValueError) as e:
        report.add(FILES, False, str(e))
        report.skip(*later)
        return report
    report.add(FILES, True, f"{csv_where}\n{result_where}\n{record.where}")

    # 1. The Seal names this Draw day and the algorithm this Verifier implements.
    seal = record.seal
    try:
        sealed_fp, sealed_count = seal["fingerprint"], int(seal["ticket_count"])
        sealed_round, sealed_chain = int(seal["drand"]["round"]), seal["drand"]["chain_hash"]
        sealed_at = datetime.fromisoformat(seal["sealed_at"])
        problems = [
            f"Seal is for {seal.get('draw_day')!r}" if seal.get("draw_day") != day else "",
            f"Seal uses scheme {seal.get('scheme')!r}, this Verifier implements {SCHEME}"
            if seal.get("scheme") != SCHEME
            else "",
            "Seal names a different drand chain" if sealed_chain != DRAND_CHAIN else "",
        ]
        problems = [p for p in problems if p]
    except (KeyError, TypeError, ValueError) as e:
        report.add(SEAL, False, f"Seal is missing or has a malformed field: {e}")
        report.skip(*later)
        return report
    kind = " (TEST day)" if seal.get("kind") == "test" else ""
    if not report.add(
        SEAL,
        not problems,
        "\n".join(problems)
        or f"{sealed_count:,} tickets, fingerprint {sealed_fp[:16]}..., drand round {sealed_round}{kind}",
    ):
        report.skip(*later)
        return report

    # 2. The Seal was recorded by GitHub before the randomness existed, and never edited.
    released = round_time(sealed_round)
    if record.published_at is None:
        report.add(
            SEAL_PROVENANCE,
            True,
            "offline mode: check the Seal's commit history on GitHub yourself",
            warn=True,
        )
    else:
        ok = record.published_at < released and record.revisions == 1
        report.add(
            SEAL_PROVENANCE,
            ok,
            f"first committed {record.published_at:%Y-%m-%d %H:%M:%S} UTC, {record.revisions} revision(s); "
            f"randomness released {released:%Y-%m-%d %H:%M:%S} UTC",
        )

    # 3. The downloaded Ticket list is exactly the sealed one.
    try:
        rows = csv_bytes.decode("utf-8").split("\n")
        tickets = [r.split(",", 1)[1] for r in rows[1:] if r]
        canonical = canonical_csv(tickets) == csv_bytes
    except (UnicodeDecodeError, IndexError, EngineError) as e:
        tickets, canonical = [], False
        report.add(TICKET_LIST, False, f"Ticket list could not be read: {e}")
    else:
        actual_fp = fingerprint(csv_bytes)
        detail = [
            f"fingerprint of downloaded list {actual_fp}",
            f"fingerprint in the Seal        {sealed_fp}",
            f"tickets: {len(tickets):,} downloaded, {sealed_count:,} sealed",
        ]
        if not canonical:
            detail.append("the file is not in the canonical layout (sorted, numbered, '\\n' line endings)")
        report.add(
            TICKET_LIST,
            canonical and actual_fp == sealed_fp and len(tickets) == sealed_count,
            "\n".join(detail),
        )

    # 4. The Randomness round was released after Entries closed, so nobody could know it then.
    report.add(
        ROUND_AFTER_SEAL,
        released > sealed_at,
        f"Entries closed {sealed_at.astimezone(UTC):%Y-%m-%d %H:%M:%S} UTC; "
        f"round {sealed_round} released {released:%Y-%m-%d %H:%M:%S} UTC",
    )

    # 5. The randomness used is drand's real value for the sealed round.
    randomness = _check_randomness(report, sources, sealed_round, result)

    # 6. Recompute the Winners and compare with the published ones.
    if randomness is None or not tickets or report.status(TICKET_LIST) != "PASS":
        report.skip(WINNERS)
        return report
    try:
        ours = pick_winners(tickets, randomness, day)
    except EngineError as e:
        report.add(WINNERS, False, str(e))
        return report
    published = [(w.get("rank"), w.get("position"), w.get("ticket")) for w in result.get("winners", [])]
    expected = [(w["rank"], w["position"], w["ticket"]) for w in ours["winners"]]
    lines = [f"#{r:<2} {t}  (position {p:,})" for r, p, t in expected]
    mismatches = [
        f"rank {e[0]}: published {p[2] if p else 'nothing'}, recomputed {e[2]}"
        for e, p in zip(expected, published + [None] * WINNER_COUNT, strict=False)
        if e != p
    ]
    if len(published) != WINNER_COUNT:
        mismatches.append(f"{len(published)} Winners published, expected {WINNER_COUNT}")
    report.add(WINNERS, not mismatches, "\n".join(mismatches or lines))
    return report


def _check_randomness(report: Report, sources, round_no: int, result: dict) -> str | None:
    responses = sources.drand(round_no)
    problems, values = [], set()
    for where, r in responses:
        try:
            if int(r["round"]) != round_no:
                problems.append(f"{where} answered round {r['round']}")
            elif hashlib.sha256(bytes.fromhex(r["signature"])).hexdigest() != r["randomness"]:
                problems.append(f"{where}: randomness is not the SHA-256 of its signature")
            else:
                values.add(r["randomness"])
        except (KeyError, TypeError, ValueError):
            problems.append(f"{where}: malformed drand response")
    if len(responses) < sources.min_drand_sources:
        problems.append(f"only {len(responses)} drand source(s) answered, need {sources.min_drand_sources}")
    if len(values) > 1:
        problems.append("drand sources disagree")
    used = result.get("drand", {})
    value = next(iter(values), None)
    if value and used.get("round") != round_no:
        problems.append(f"result used round {used.get('round')}, the Seal names round {round_no}")
    if value and used.get("randomness") != value:
        problems.append("result used different randomness from drand's")
    detail = f"round {round_no} from {len(responses)} source(s): {value or 'none'}"
    report.add(RANDOMNESS, not problems and value is not None, "\n".join([detail, *problems]))
    return value if not problems else None


# --------------------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check a past Boche Lucky Draw result independently.")
    parser.add_argument("draw_day", help="the Draw day to check, e.g. 2026-11-10 (or a Test day label)")
    parser.add_argument(
        "--site", default=DEFAULT_SITE, help=f"Boche site to download from (default {DEFAULT_SITE})"
    )
    parser.add_argument(
        "--seals-repo", default=DEFAULT_SEALS_REPO, help="GitHub owner/repo holding the Seals"
    )
    parser.add_argument("--from-dir", help="check files saved in this folder instead of downloading them")
    args = parser.parse_args(argv)

    sources = FolderSources(args.from_dir) if args.from_dir else LiveSources(args.site, args.seals_repo)
    report = verify(args.draw_day, sources)
    print(report.render())
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
