"""drand quicknet, the draw's only source of randomness (ADR-0002). Values match verifier/verify.py."""

from datetime import UTC, datetime, timedelta

CHAIN_HASH = "52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971"
GENESIS = 1692803367  # Unix time of round 1
PERIOD = 3  # seconds between rounds
SAFETY_MARGIN = timedelta(seconds=30)  # a late seal names a round at least this far in the future


def round_released_at(round_no: int) -> datetime:
    return datetime.fromtimestamp(GENESIS + (round_no - 1) * PERIOD, tz=UTC)


def first_round_at_or_after(t: datetime) -> int:
    """The earliest round whose value is released at or after time t."""
    seconds = int(t.timestamp()) + (1 if t.microsecond else 0) - GENESIS
    return max(1, -(-seconds // PERIOD) + 1)


def round_for_seal(draw_not_before: datetime, sealed_at: datetime) -> int:
    """The Randomness round a Seal names: the one released at the scheduled draw time (8:15 PM IST),
    or, if sealing happens late, one still safely in the future. The list is always fixed before the
    value exists."""
    return max(first_round_at_or_after(draw_not_before), first_round_at_or_after(sealed_at + SAFETY_MARGIN))
