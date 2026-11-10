"""The Verifier carries its own copy of the draw logic. These tests keep it identical to the engine."""

import hashlib
import json
from pathlib import Path

import engine
import verify

VECTOR = json.loads(
    (Path(__file__).resolve().parents[2] / "engine" / "tests" / "known_answer_v1.json").read_text(
        encoding="utf-8"
    )
)


def test_verifier_reproduces_the_published_known_answer_vector():
    result = verify.pick_winners(VECTOR["tickets"], VECTOR["randomness"], VECTOR["draw_day"])
    assert result["fingerprint"] == VECTOR["fingerprint"]
    assert result["seed"] == VECTOR["seed"]
    assert [[w["rank"], w["position"], w["ticket"]] for w in result["winners"]] == VECTOR["winners"]


def test_verifier_and_engine_agree_on_many_random_draws():
    for i in range(200):
        n = 10 + i * 7
        tickets = [hashlib.sha256(f"{i}-{k}".encode()).hexdigest()[:8].upper() for k in range(n)]
        randomness = hashlib.sha256(f"r{i}".encode()).hexdigest()
        day = f"2026-11-{1 + i % 28:02d}"
        ours = verify.pick_winners(tickets, randomness, day)
        theirs = engine.pick_winners(tickets, randomness, day)
        assert ours["fingerprint"] == theirs.fingerprint
        assert ours["seed"] == theirs.seed
        assert [(w["rank"], w["prize"], w["position"], w["ticket"]) for w in ours["winners"]] == [
            (w.rank, w.prize, w.position, w.ticket) for w in theirs.winners
        ]


def test_verifier_imports_nothing_outside_the_standard_library():
    import sys

    source = Path(verify.__file__).read_text(encoding="utf-8")
    imported = {
        line.split()[1].split(".")[0] for line in source.splitlines() if line.startswith(("import ", "from "))
    }
    assert imported <= set(sys.stdlib_module_names) | {"__future__"}, imported
