"""Fetching a drand round from public relays: at least two must agree, and each value must check out."""

import hashlib

import pytest

from app.draw.drand import CHAIN_HASH, DrandUnavailable, fetch_round

RELAYS = ["https://r1.example", "https://r2.example", "https://r3.example"]


def good(round_no, salt=""):
    sig = hashlib.sha256(f"sig{round_no}{salt}".encode()).hexdigest() * 3
    return {"round": round_no, "randomness": hashlib.sha256(bytes.fromhex(sig)).hexdigest(), "signature": sig}


def http_from(answers):
    def get(url):
        base = url.split(f"/{CHAIN_HASH}/")[0]
        answer = answers.get(base)
        if answer is None:
            raise OSError("unreachable")
        return answer

    return get


def test_two_agreeing_relays_give_the_round():
    value = fetch_round(7, RELAYS, http=http_from({RELAYS[0]: good(7), RELAYS[2]: good(7)}))
    assert value == good(7)


def test_one_relay_alone_is_not_enough():
    with pytest.raises(DrandUnavailable):
        fetch_round(7, RELAYS, http=http_from({RELAYS[0]: good(7)}))


def test_relays_that_disagree_are_refused():
    with pytest.raises(DrandUnavailable):
        fetch_round(7, RELAYS, http=http_from({RELAYS[0]: good(7), RELAYS[1]: good(7, "x")}))


def test_a_value_that_is_not_the_hash_of_its_signature_is_ignored():
    forged = {**good(7), "randomness": "00" * 32}
    with pytest.raises(DrandUnavailable):
        fetch_round(7, RELAYS, http=http_from({RELAYS[0]: good(7), RELAYS[1]: forged}))


def test_an_answer_for_another_round_is_ignored():
    with pytest.raises(DrandUnavailable):
        fetch_round(7, RELAYS, http=http_from({RELAYS[0]: good(7), RELAYS[1]: good(8)}))
