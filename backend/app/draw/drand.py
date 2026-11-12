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
    """The Randomness round a Seal names: the one released at the scheduled draw time (10:15 PM IST),
    or, if sealing happens late, one still safely in the future. The list is always fixed before the
    value exists."""
    return max(first_round_at_or_after(draw_not_before), first_round_at_or_after(sealed_at + SAFETY_MARGIN))


# ------------------------------------------------------------------ fetching a round

RELAYS = [
    "https://api.drand.sh",
    "https://api2.drand.sh",
    "https://api3.drand.sh",
    "https://drand.cloudflare.com",
]
MIN_AGREEING_RELAYS = 2


class DrandUnavailable(Exception):
    """Not enough independent relays returned a valid, matching value for the round."""


def _get_json(url: str) -> dict:
    import requests

    res = requests.get(url, timeout=10, headers={"User-Agent": "boche-lucky-draw"})
    res.raise_for_status()
    return res.json()


def fetch_round(round_no: int, relays: list[str] = RELAYS, http=_get_json) -> dict:
    """The value of one drand round, confirmed by at least two independent relays.

    Each answer must be for the requested round, and its randomness must be the SHA-256 of its
    signature (how drand defines it). Full BLS signature checking is left to the Verifier's users
    (see verifier/README.md)."""
    import hashlib

    agreed: dict[tuple[str, str], int] = {}
    for base in relays:
        try:
            r = http(f"{base}/{CHAIN_HASH}/public/{round_no}")
            sig, rnd = str(r["signature"]), str(r["randomness"])
            if int(r["round"]) != round_no or hashlib.sha256(bytes.fromhex(sig)).hexdigest() != rnd:
                continue
        except Exception:  # an unreachable or malformed relay simply doesn't count
            continue
        agreed[(rnd, sig)] = agreed.get((rnd, sig), 0) + 1
    if len(agreed) != 1 or next(iter(agreed.values())) < MIN_AGREEING_RELAYS:
        raise DrandUnavailable(
            f"round {round_no}: relays unavailable or in disagreement ({len(agreed)} values)"
        )
    (rnd, sig), _ = next(iter(agreed.items()))
    return {"round": round_no, "randomness": rnd, "signature": sig}
