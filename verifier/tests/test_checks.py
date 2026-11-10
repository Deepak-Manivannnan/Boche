"""The Verifier's checks, run against a folder of a Draw day's public files (offline mode)."""

import json

from drawfiles import DAY, drand_response

import verify


def run(draw) -> verify.Report:
    return verify.verify(DAY, verify.FolderSources(draw.folder))


def status(report: verify.Report) -> dict[str, str]:
    return {c.name: c.status for c in report.checks}


def test_a_genuine_draw_passes_every_check(draw):
    report = run(draw)
    assert report.ok, report.render()
    assert set(status(report).values()) <= {"PASS", "WARN"}
    assert all(s == "PASS" for name, s in status(report).items() if name != verify.SEAL_PROVENANCE)


def test_offline_mode_warns_that_the_seal_time_comes_from_the_file_not_github(draw):
    assert status(run(draw))[verify.SEAL_PROVENANCE] == "WARN"


def test_a_ticket_added_after_the_seal_fails_the_ticket_list_check(draw):
    rows = draw.csv.decode().splitlines()
    rows.append(f"{len(rows)},ZZ 999999")
    draw.csv = ("\n".join(rows) + "\n").encode()
    draw.save()
    report = run(draw)
    assert not report.ok
    assert status(report)[verify.TICKET_LIST] == "FAIL"
    assert report.first_failure().name == verify.TICKET_LIST


def test_a_ticket_swapped_after_the_seal_fails_even_if_the_count_is_unchanged(draw):
    draw.csv = draw.csv.replace(b"AB 000150", b"ZZ 000150")
    draw.save()
    assert status(run(draw))[verify.TICKET_LIST] == "FAIL"


def test_a_list_that_is_not_in_the_canonical_layout_fails(draw):
    draw.csv = draw.csv.replace(b"\n", b"\r\n")
    draw.seal["fingerprint"] = __import__("hashlib").sha256(draw.csv).hexdigest()
    draw.save()
    assert status(run(draw))[verify.TICKET_LIST] == "FAIL"


def test_a_published_winner_that_the_engine_did_not_pick_fails_the_winners_check(draw):
    draw.result["winners"][0]["ticket"] = (
        "AB 000001" if draw.result["winners"][0]["ticket"] != "AB 000001" else "AB 000002"
    )
    draw.save()
    report = run(draw)
    assert status(report)[verify.WINNERS] == "FAIL"
    assert status(report)[verify.TICKET_LIST] == "PASS"
    assert status(report)[verify.RANDOMNESS] == "PASS"


def test_winners_published_in_a_different_order_fail(draw):
    w = draw.result["winners"]
    w[0]["ticket"], w[1]["ticket"] = w[1]["ticket"], w[0]["ticket"]
    draw.save()
    assert status(run(draw))[verify.WINNERS] == "FAIL"


def test_a_result_that_used_a_different_randomness_round_fails(draw):
    other = drand_response(draw.seal["drand"]["round"] + 1)
    draw.result["drand"].update(other)
    draw.save()
    report = run(draw)
    assert status(report)[verify.RANDOMNESS] == "FAIL"


def test_randomness_that_is_not_the_hash_of_its_signature_fails(draw):
    draw.drand["randomness"] = "00" * 32
    draw.result["drand"]["randomness"] = "00" * 32
    draw.save()
    assert status(run(draw))[verify.RANDOMNESS] == "FAIL"


def test_a_seal_naming_a_round_released_before_entries_closed_fails(draw):
    # Round 1 was released in 2023: its value was already public, so it could be chosen to suit.
    draw.seal["drand"]["round"] = 1
    draw.result["drand"].update(drand_response(1))
    draw.drand = drand_response(1)
    draw.save()
    assert status(run(draw))[verify.ROUND_AFTER_SEAL] == "FAIL"


def test_a_seal_for_a_different_draw_day_fails(draw):
    draw.seal["draw_day"] = "2026-11-09"
    draw.save()
    assert status(run(draw))[verify.SEAL] == "FAIL"


def test_a_missing_file_is_reported_as_a_failure_not_a_crash(draw):
    (draw.folder / "result.json").unlink()
    report = run(draw)
    assert not report.ok
    assert "result.json" in report.render()


def test_report_text_names_every_check(draw):
    text = run(draw).render()
    for name in (verify.SEAL, verify.TICKET_LIST, verify.ROUND_AFTER_SEAL, verify.RANDOMNESS, verify.WINNERS):
        assert name in text


def test_the_result_json_round_trip_is_plain_json(draw):
    assert json.loads((draw.folder / "result.json").read_text())["draw_day"] == DAY
