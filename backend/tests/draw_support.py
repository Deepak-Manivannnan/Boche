"""Test helpers for a Draw day that has closed: fake OTP sender, fake drand, and a ready-made sealed day."""

import hashlib
import re
from dataclasses import replace
from types import SimpleNamespace

from test_entries_api import at, enter
from test_orders_api import buy

from app.draw.drand import DrandUnavailable

DAY = "2026-11-10"


class FakeOtp:
    def __init__(self):
        self.sent = []

    def send(self, to, text):
        self.sent.append((to, text))

    @property
    def code(self):
        return re.search(r"OTP (\d{6})\b", self.sent[-1][1]).group(1)


def drand_value(round_no):
    sig = hashlib.sha256(f"sig-{round_no}".encode()).hexdigest() * 3
    return {"round": round_no, "randomness": hashlib.sha256(bytes.fromhex(sig)).hexdigest(), "signature": sig}


class FakeDrand:
    def __init__(self):
        self.down = False

    def __call__(self, round_no):
        if self.down:
            raise DrandUnavailable("relays unreachable")
        return drand_value(round_no)


def sealed_day(make_client, packs=2, single_cards=0):
    """Arun enters `packs` x 1 kg (8 Tickets each) and `single_cards` x 250 g (1 Ticket each) before 8 PM;
    the day is sealed at 8:00:01 PM IST."""
    arun, admin = make_client("arun"), make_client("admin")
    state = admin.app.state
    state.otp_sender, state.drand_fetch, state.seal_publisher = FakeOtp(), FakeDrand(), None
    state.settings = replace(state.settings, founder_mobile="+919800000000")
    at(arun, 18, 0)
    numbers, cards = [], []
    for items in [{"p1k": 1}] * packs + [{"p250": 1}] * single_cards:
        for card in buy(arun, items)["cards"]:
            assert enter(arun, card["id"]).status_code == 200
            numbers += card["numbers"]
            cards.append(card)
    at(arun, 20, 0, 1)
    arun.post("/api/tick")
    return SimpleNamespace(arun=arun, admin=admin, state=state, numbers=numbers, cards=cards)


def draw(w, hh=20, mm=16):
    """Request the Founder's OTP and run the draw at hh:mm IST."""
    at(w.admin, hh, mm)
    assert w.admin.post(f"/api/admin/draw-days/{DAY}/otp").status_code == 200
    res = w.admin.post(f"/api/admin/draw-days/{DAY}/run", json={"code": w.state.otp_sender.code})
    assert res.status_code == 200, res.text
    return res.json()
