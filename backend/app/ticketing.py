"""Lucky numbers: drawn by the server with a cryptographically secure generator, never by the browser.
The database's unique constraint is the final guarantee that no number is issued twice."""

import secrets
from collections.abc import Callable, Iterable

from app.catalog import LETTERS

MAX_ROUNDS = 100


def new_lucky_number(rand: Callable[[int], int] = secrets.randbelow) -> str:
    """Two letters and six digits, e.g. "AB 012345" (23 x 23 x 1,000,000 = 529 million possibilities)."""
    return f"{LETTERS[rand(len(LETTERS))]}{LETTERS[rand(len(LETTERS))]} {rand(1_000_000):06d}"


def unique_numbers(
    count: int,
    already_taken: Callable[[list[str]], Iterable[str]],
    rand: Callable[[int], int] = secrets.randbelow,
) -> list[str]:
    """`count` new numbers, distinct from each other and from every number `already_taken` reports."""
    batch: list[str] = []
    seen: set[str] = set()
    for _ in range(count):
        batch.append(_fresh(seen, rand))
    for _ in range(MAX_ROUNDS):
        taken = set(already_taken(batch))
        if not taken:
            return batch
        for i, number in enumerate(batch):
            if number in taken:
                batch[i] = _fresh(seen, rand)
    raise RuntimeError("could not find unused lucky numbers")


def _fresh(seen: set[str], rand) -> str:
    for _ in range(MAX_ROUNDS):
        number = new_lucky_number(rand)
        if number not in seen:
            seen.add(number)
            return number
    raise RuntimeError("could not find unused lucky numbers")
