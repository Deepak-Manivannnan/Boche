"""The frontend turns /api/me/orders into the order shape the prototype's screens already read.
Runs the real fromServerOrder() from app.js in Node on a real API response."""

import json
import re
import shutil
import subprocess

import pytest
from test_orders_api import DELIVERY, buy

from app.main import FRONTEND_DIR


def run_adapter(server_order: dict, card_local: dict) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    source = (FRONTEND_DIR / "app.js").read_text(encoding="utf-8")
    fn = re.search(r"  function fromServerOrder\(o\) \{.*?\n  \}\r?\n", source, re.S).group(0)
    script = (
        f"var LOCAL = {json.dumps(card_local)}; function cardLocal() {{ return LOCAL; }}\n{fn}\n"
        f"console.log(JSON.stringify(fromServerOrder({json.dumps(server_order)})));"
    )
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_server_orders_become_the_prototypes_order_shape(make_client):
    paid = buy(make_client(), {"p1k": 1, "p250": 2})
    first_card = paid["cards"][0]["id"]
    o = run_adapter(paid, {first_card: {"submitted": True, "drawDate": "2026-11-10"}})

    assert o["id"] == paid["id"]
    assert re.fullmatch(r"\d{2} \w{3,4} \d{4}", o["date"])
    assert o["items"] == [{"size": "250 g", "qty": 2, "price": 90}, {"size": "1 kg", "qty": 1, "price": 320}]
    # Rs 500 tea, Rs 124 logistics; GST 25.00 + 22.32 = 47.32 -> Rs 48
    assert (o["tea"], o["logistics"], o["tax"], o["total"]) == (500, 124, 48, 672)
    assert o["gst"] == {"tea": 25, "log": 22.32, "total": 48}
    assert o["addr"] == {k: DELIVERY[k] for k in ("pin", "name", "house", "street")}
    assert o["area"] == {"po": DELIVERY["po"], "district": DELIVERY["district"]}
    assert [c["pack"] for c in o["cards"]] == ["250 g", "250 g", "1 kg"]
    assert [len(c["nos"]) for c in o["cards"]] == [1, 1, 8]
    assert o["cards"][0]["submitted"] is True and o["cards"][0]["drawDate"] == "2026-11-10"
    assert o["cards"][1]["submitted"] is False and o["cards"][1]["drawDate"] is None
