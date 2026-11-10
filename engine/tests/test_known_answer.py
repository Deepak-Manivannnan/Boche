import json
from pathlib import Path

from engine import pick_winners

VECTOR = json.loads((Path(__file__).parent / "known_answer_v1.json").read_text(encoding="utf-8"))


def test_engine_reproduces_the_published_known_answer_vector():
    result = pick_winners(VECTOR["tickets"], VECTOR["randomness"], VECTOR["draw_day"])
    assert result.fingerprint == VECTOR["fingerprint"]
    assert result.seed == VECTOR["seed"]
    assert [[w.rank, w.position, w.ticket] for w in result.winners] == VECTOR["winners"]
