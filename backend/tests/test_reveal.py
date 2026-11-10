"""Ticket 13: the reveal's order and personalised ending, run in Node from frontend/reveal.js."""

import json
import shutil
import subprocess

import pytest

from app.main import FRONTEND_DIR

WINNERS = [
    {"rank": r, "prize": "main" if r <= 3 else "consolation", "ticket": f"AB {r:06d}",
     "label": {1: "1st prize", 2: "2nd prize", 3: "3rd prize"}.get(r, "Lucky 7"),
     "amount": {1: 100000, 2: 50000, 3: 25000}.get(r, 10000), "name": "Test C.", "position": r}
    for r in range(1, 11)
]


def plan(winners, mine, *, frame=None):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    call = (f"R.scrambleFrame({json.dumps(frame[0])}, {frame[1]}, {frame[2]})" if frame
            else f"R.plan({json.dumps(winners)}, {json.dumps(mine)})")
    script = (
        "const vm=require('vm'),fs=require('fs');const c={window:{}};vm.createContext(c);"
        f"vm.runInContext(fs.readFileSync({json.dumps(str(FRONTEND_DIR / 'reveal.js'))},'utf8'),c);"
        f"const R=c.window.BCREVEAL;console.log(JSON.stringify({call}));"
    )
    return json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout)


def test_winners_are_revealed_from_the_seventh_consolation_up_to_the_first_prize():
    p = plan(list(reversed(WINNERS)), [])
    assert [x["rank"] for x in p["order"]] == [10, 9, 8, 7, 6, 5, 4, 3, 2, 1]
    assert [x["big"] for x in p["order"]] == [False] * 7 + [True] * 3  # balloons for the main prizes


def test_a_customer_who_won_gets_a_personal_celebration_with_their_total():
    p = plan(WINNERS, ["AB 000002", "AB 000009", "ZZ 999999"])
    assert p["outcome"]["won"] is True
    assert p["outcome"]["amount"] == 60000
    assert p["outcome"]["best"] == "2nd prize"
    assert [x["mine"] for x in p["order"] if x["mine"]] and sum(x["mine"] for x in p["order"]) == 2


def test_everyone_else_gets_a_better_luck_message():
    p = plan(WINNERS, ["ZZ 000001"])
    assert p["outcome"] == {"won": False, "amount": 0, "best": None, "entered": True}
    assert plan(WINNERS, [])["outcome"]["entered"] is False


def test_the_digit_roll_locks_one_character_at_a_time_and_keeps_the_space():
    target = "KM 482913"
    assert plan(None, None, frame=[target, 0, 0.42])[2] == " "
    half = plan(None, None, frame=[target, 4, 0.42])
    assert half[:4] == "KM 4" and len(half) == len(target)
    assert plan(None, None, frame=[target, len(target), 0.42]) == target
