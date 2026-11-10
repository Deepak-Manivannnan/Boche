import pytest

from engine import EngineError, canonical_csv, fingerprint, pick_winners

RANDOMNESS = "a1" * 32  # 32 bytes of hex, the shape of a drand quicknet round value
DAY = "2026-11-10"


def tickets(n: int) -> list[str]:
    return [f"AB {i:06d}" for i in range(1, n + 1)]


def test_ten_distinct_winners_are_picked_from_the_list():
    pool = tickets(500)
    result = pick_winners(pool, RANDOMNESS, DAY)
    picked = [w.ticket for w in result.winners]
    assert len(picked) == 10
    assert len(set(picked)) == 10
    assert set(picked) <= set(pool)


def test_first_three_win_main_prizes_and_next_seven_win_consolation_prizes():
    result = pick_winners(tickets(500), RANDOMNESS, DAY)
    assert [w.rank for w in result.winners] == list(range(1, 11))
    assert [w.prize for w in result.winners] == ["main"] * 3 + ["consolation"] * 7


def test_each_winner_carries_its_position_in_the_published_list():
    pool = tickets(500)
    csv_rows = canonical_csv(pool).decode().splitlines()[1:]
    for w in pick_winners(pool, RANDOMNESS, DAY).winners:
        assert csv_rows[w.position - 1] == f"{w.position},{w.ticket}"


def test_running_the_draw_again_gives_the_same_winners():
    pool = tickets(5000)
    assert pick_winners(pool, RANDOMNESS, DAY) == pick_winners(list(reversed(pool)), RANDOMNESS, DAY)


def test_result_reports_the_fingerprint_of_the_list_it_drew_from():
    pool = tickets(50)
    assert pick_winners(pool, RANDOMNESS, DAY).fingerprint == fingerprint(canonical_csv(pool))


def test_different_randomness_gives_different_winners():
    pool = tickets(5000)
    a = pick_winners(pool, RANDOMNESS, DAY).winners
    b = pick_winners(pool, "b2" * 32, DAY).winners
    assert a != b


def test_same_randomness_on_a_different_draw_day_gives_different_winners():
    pool = tickets(5000)
    assert pick_winners(pool, RANDOMNESS, DAY).winners != pick_winners(pool, RANDOMNESS, "2026-11-11").winners


def test_fewer_than_ten_tickets_cannot_be_drawn():
    with pytest.raises(EngineError, match="at least 10"):
        pick_winners(tickets(9), RANDOMNESS, DAY)


def test_exactly_ten_tickets_all_win():
    pool = tickets(10)
    assert sorted(w.ticket for w in pick_winners(pool, RANDOMNESS, DAY).winners) == pool


@pytest.mark.parametrize("bad", ["", "xyz", "abc"])
def test_randomness_must_be_hex(bad):
    with pytest.raises(EngineError, match="randomness"):
        pick_winners(tickets(20), bad, DAY)


@pytest.mark.parametrize("bad", ["", "2026|11|10"])
def test_draw_day_must_be_a_plain_label(bad):
    with pytest.raises(EngineError, match="draw day"):
        pick_winners(tickets(20), RANDOMNESS, bad)
