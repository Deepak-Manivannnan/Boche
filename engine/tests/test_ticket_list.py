import hashlib

import pytest

from engine import EngineError, canonical_csv, fingerprint


def test_canonical_csv_sorts_tickets_and_numbers_positions_from_one():
    csv = canonical_csv(["CD 000002", "AB 000001", "EF 000003"])
    assert csv == b"position,ticket_number\n1,AB 000001\n2,CD 000002\n3,EF 000003\n"


def test_canonical_csv_is_the_same_whatever_order_tickets_arrive_in():
    assert canonical_csv(["B 2", "A 1", "C 3"]) == canonical_csv(["C 3", "B 2", "A 1"])


def test_duplicate_ticket_is_rejected():
    with pytest.raises(EngineError, match="duplicate"):
        canonical_csv(["AB 000001", "AB 000001"])


@pytest.mark.parametrize("bad", ["", "AB,1", "AB\n1", "AB\r1"])
def test_ticket_that_would_break_the_csv_is_rejected(bad):
    with pytest.raises(EngineError):
        canonical_csv(["AB 000001", bad])


def test_fingerprint_is_sha256_hex_of_the_list_bytes():
    # Known SHA-256 test vector for "abc" (FIPS 180-2).
    assert fingerprint(b"abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_changing_one_ticket_changes_the_fingerprint():
    tickets = [f"AB {i:06d}" for i in range(1, 1001)]
    changed = tickets.copy()
    changed[500] = "ZZ 999999"
    assert fingerprint(canonical_csv(tickets)) != fingerprint(canonical_csv(changed))


def test_fingerprint_matches_an_independent_sha256_of_the_published_file():
    csv = canonical_csv(["AB 000001", "CD 000002"])
    assert (
        fingerprint(csv) == hashlib.sha256(b"position,ticket_number\n1,AB 000001\n2,CD 000002\n").hexdigest()
    )
