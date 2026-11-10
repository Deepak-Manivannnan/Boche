"""The server's Pack table and lucky-number rules, checked against the prototype's data.js."""

import json
import shutil
import subprocess

import pytest

from app.catalog import LETTERS, LOGISTICS_GST_RATE, MAX_QTY, PACKS, TEA_GST_RATE, quote
from app.main import FRONTEND_DIR
from app.ticketing import new_lucky_number, unique_numbers


def prototype_data() -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = (
        "const vm=require('vm'),fs=require('fs');const c={};vm.createContext(c);"
        f"vm.runInContext(fs.readFileSync({json.dumps(str(FRONTEND_DIR / 'data.js'))},'utf8'),c);"
        "console.log(JSON.stringify({tea:c.BC_TEA,letters:c.BC_DRAW.letters}))"
    )
    return json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout)


def test_server_pack_table_matches_the_prototypes_data_js():
    data = prototype_data()
    tea = data["tea"]
    assert {p["id"] for p in tea["packs"]} == set(PACKS)
    for p in tea["packs"]:
        pack = PACKS[p["id"]]
        assert (pack.size, pack.price_paise, pack.numbers, pack.logistics_paise) == (
            p["size"],
            p["price"] * 100,
            p["numbers"],
            p["logistics"] * 100,
        )
    assert (MAX_QTY, TEA_GST_RATE, LOGISTICS_GST_RATE) == (
        tea["maxQty"],
        tea["taxRate"],
        tea["logisticsTaxRate"],
    )
    assert data["letters"] == LETTERS


def test_quote_counts_one_ticket_per_lucky_number():
    q = quote({"p1k": 2, "p500": 1, "p250": 3})
    assert q.ticket_count == 2 * 8 + 3 + 3


class ScriptedRandom:
    """Plays back fixed values for randbelow(), so a collision can be forced."""

    def __init__(self, values):
        self.values = list(values)

    def __call__(self, n):
        return self.values.pop(0) % n


def test_a_lucky_number_is_two_letters_and_six_digits():
    assert new_lucky_number(ScriptedRandom([0, 22, 42])) == "AZ 000042"


def test_numbers_already_taken_or_repeated_in_the_batch_are_drawn_again():
    # Each number uses three draws: letter, letter, digits. The script repeats 000001 and 000002 inside
    # the batch, and 000001 is already taken in the database, so the expected result is fully determined.
    rand = ScriptedRandom([0, 0, 1, 0, 0, 1, 0, 0, 2, 0, 0, 2, 0, 0, 3, 0, 0, 4])
    picked = unique_numbers(3, already_taken=lambda batch: {"AA 000001"} & set(batch), rand=rand)
    assert picked == ["AA 000004", "AA 000002", "AA 000003"]


def test_drawing_gives_up_loudly_rather_than_looping_forever():
    with pytest.raises(RuntimeError):
        unique_numbers(1, already_taken=lambda batch: set(batch), rand=lambda n: 0)
