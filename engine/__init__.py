"""Boche lucky-draw engine.

Pure Python, standard library only: no database, network or clock. Given a Draw day's
Tickets and the drand Randomness round value, it always produces the same ten Winners.
The Verifier carries a copy of this module so outsiders can recompute any draw.
"""

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass

CSV_HEADER = "position,ticket_number"
SCHEME = "boche-draw-v1"  # changes only if the algorithm changes; old draws keep verifying
WINNER_COUNT = 10
MAIN_PRIZES = 3


class EngineError(ValueError):
    """Raised when the engine is given input it must not draw from."""


def canonical_csv(tickets: Iterable[str]) -> bytes:
    """The one published layout of a Ticket list: sorted, numbered from 1, '\\n' endings, UTF-8.

    Every machine must produce the same bytes from the same Tickets, because the
    Fingerprint is computed over these bytes (ADR-0007).
    """
    ordered = sorted(tickets)
    for i, ticket in enumerate(ordered):
        if not ticket or any(ch in ticket for ch in ",\n\r"):
            raise EngineError(f"ticket {ticket!r} is empty or contains a comma or line break")
        if i and ordered[i - 1] == ticket:
            raise EngineError(f"duplicate ticket {ticket!r}")
    lines = [CSV_HEADER] + [f"{pos},{ticket}" for pos, ticket in enumerate(ordered, start=1)]
    return ("\n".join(lines) + "\n").encode("utf-8")


def fingerprint(csv_bytes: bytes) -> str:
    """SHA-256 of the published Ticket list, as lowercase hex."""
    return hashlib.sha256(csv_bytes).hexdigest()


@dataclass(frozen=True)
class Winner:
    rank: int  # 1..10, in the order picked
    prize: str  # "main" for ranks 1-3, "consolation" for ranks 4-10
    position: int  # 1-based row in the published Ticket list
    ticket: str


@dataclass(frozen=True)
class DrawResult:
    draw_day: str
    fingerprint: str
    randomness: str
    seed: str
    winners: tuple[Winner, ...]


def derive_seed(randomness: str, list_fingerprint: str, draw_day: str) -> bytes:
    """One 32-byte seed from the three public inputs. Hex and dates never contain '|'."""
    text = f"{SCHEME}|{randomness}|{list_fingerprint}|{draw_day}"
    return hashlib.sha256(text.encode("ascii")).digest()


def unbiased_index(seed: bytes, pick: int, n: int) -> int:
    """A uniformly random index in [0, n) for the given pick, with no modulo bias.

    Each attempt hashes (seed, pick, attempt) to a 256-bit number. Numbers at or above the
    largest multiple of n below 2**256 are rejected and the next attempt is tried, so every
    index has exactly the same number of accepted values. With n <= 100,000 a rejection
    happens with probability below 2**-239, but the rule keeps the draw exactly fair.
    """
    limit = (1 << 256) - ((1 << 256) % n)
    attempt = 0
    while True:
        h = int.from_bytes(
            hashlib.sha256(seed + f"|pick:{pick}|try:{attempt}".encode("ascii")).digest(), "big"
        )
        if h < limit:
            return h % n
        attempt += 1


def pick_winners(
    tickets: Iterable[str], randomness: str, draw_day: str, count: int = WINNER_COUNT
) -> DrawResult:
    """Pick `count` distinct Winners from a Draw day's Tickets.

    The only inputs are the Ticket list (sealed when Entries close), the drand Randomness
    round value named in the Seal, and the Draw day label. The same inputs always give the
    same Winners, so a re-run or a restart after a crash cannot change the result.
    """
    _check_randomness(randomness)
    if not draw_day or "|" in draw_day:
        raise EngineError(f"draw day {draw_day!r} must be a non-empty label without '|'")

    csv = canonical_csv(tickets)
    ordered = [line.split(",", 1)[1] for line in csv.decode("utf-8").splitlines()[1:]]
    if len(ordered) < count:
        raise EngineError(f"a draw needs at least {count} tickets, got {len(ordered)}")

    list_fp = fingerprint(csv)
    seed = derive_seed(randomness, list_fp, draw_day)
    remaining = list(range(1, len(ordered) + 1))  # positions still in the draw
    winners = []
    for rank in range(1, count + 1):
        position = remaining.pop(unbiased_index(seed, rank, len(remaining)))
        prize = "main" if rank <= MAIN_PRIZES else "consolation"
        winners.append(Winner(rank=rank, prize=prize, position=position, ticket=ordered[position - 1]))

    return DrawResult(draw_day, list_fp, randomness, seed.hex(), tuple(winners))


def _check_randomness(randomness: str) -> None:
    try:
        ok = len(randomness) > 0 and len(randomness) % 2 == 0 and bytes.fromhex(randomness) is not None
    except ValueError:
        ok = False
    if not ok or randomness != randomness.lower():
        raise EngineError(f"randomness {randomness!r} must be non-empty lowercase hex")
