"""Fairness and scale properties from the brief. Inputs are fixed, so these tests are deterministic."""

import hashlib
import time
from collections import Counter

from engine import pick_winners

DAY = "2026-11-10"


def randomness(i: int) -> str:
    return hashlib.sha256(f"round-{i}".encode()).hexdigest()


def tickets(n: int) -> list[str]:
    return [f"AB {i:06d}" for i in range(1, n + 1)]


def chi_square(counts: Counter, categories: list[str], expected: float) -> float:
    return sum((counts[c] - expected) ** 2 / expected for c in categories)


def test_every_ticket_is_equally_likely_to_win_first_prize():
    pool = tickets(20)
    draws = 4000
    firsts = Counter(pick_winners(pool, randomness(i), DAY).winners[0].ticket for i in range(draws))
    # 19 degrees of freedom; 43.82 is the critical value at p = 0.001.
    assert chi_square(firsts, pool, draws / len(pool)) < 43.82


def test_every_ticket_is_equally_likely_to_win_the_last_consolation_prize():
    pool = tickets(20)
    draws = 4000
    lasts = Counter(pick_winners(pool, randomness(i), DAY).winners[9].ticket for i in range(draws))
    assert chi_square(lasts, pool, draws / len(pool)) < 43.82


def test_a_customer_with_three_tickets_wins_about_three_times_as_often_as_one_with_one():
    pool = tickets(40)
    alice, bob = set(pool[:3]), {pool[3]}
    alice_wins = bob_wins = 0
    for i in range(3000):
        won = {w.ticket for w in pick_winners(pool, randomness(i), DAY).winners}
        alice_wins += len(won & alice)
        bob_wins += len(won & bob)
    assert 2.6 < alice_wins / bob_wins < 3.4


def test_a_draw_over_100000_tickets_takes_under_two_seconds():
    pool = [f"{chr(65 + i % 23)}{chr(65 + i // 23 % 23)} {i:06d}" for i in range(100_000)]
    start = time.perf_counter()
    result = pick_winners(pool, randomness(1), DAY)
    elapsed = time.perf_counter() - start
    assert len(result.winners) == 10
    assert elapsed < 2.0, f"took {elapsed:.2f}s"
