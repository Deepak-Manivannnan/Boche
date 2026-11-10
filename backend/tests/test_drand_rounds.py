"""The backend's drand round arithmetic must agree with the Verifier's."""

from datetime import UTC, datetime, timedelta

import verify
from app.drand import CHAIN_HASH, GENESIS, PERIOD, first_round_at_or_after, round_for_seal, round_released_at


def test_the_backend_and_the_verifier_use_the_same_drand_chain():
    assert (CHAIN_HASH, GENESIS, PERIOD) == (verify.DRAND_CHAIN, verify.DRAND_GENESIS, verify.DRAND_PERIOD)


def test_round_release_times_agree_with_the_verifier():
    for r in (1, 2, 1000, 33_839_512):
        assert round_released_at(r) == verify.round_time(r)


def test_the_first_round_at_or_after_a_time_is_never_early_and_at_most_three_seconds_late():
    start = datetime(2026, 11, 10, 14, 45, tzinfo=UTC)
    for ms in range(0, 6000, 250):
        t = start + timedelta(milliseconds=ms)
        released = round_released_at(first_round_at_or_after(t))
        assert t <= released < t + timedelta(seconds=PERIOD)


def test_a_seal_on_time_names_the_eight_fifteen_round():
    draw = datetime(2026, 11, 10, 14, 45, tzinfo=UTC)
    assert round_for_seal(draw, datetime(2026, 11, 10, 14, 30, 1, tzinfo=UTC)) == first_round_at_or_after(
        draw
    )


def test_a_late_seal_names_a_round_at_least_thirty_seconds_ahead():
    draw = datetime(2026, 11, 10, 14, 45, tzinfo=UTC)
    late = datetime(2026, 11, 10, 14, 50, tzinfo=UTC)
    assert round_released_at(round_for_seal(draw, late)) >= late + timedelta(seconds=30)
