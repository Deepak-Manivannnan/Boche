"""Published results: the Verifier's result.json, and the masked winner details shown in the app."""

import re

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.db import models as m
from app.draw.drand import CHAIN_HASH
from app.shop.catalog import prize
from engine import SCHEME


def mask_name(name: str) -> str:
    """First name and last initial, e.g. "Arun Mathew" -> "Arun M."."""
    parts = name.split()
    if not parts:
        return "Boche member"
    return parts[0] if len(parts) == 1 else f"{parts[0]} {parts[-1][0].upper()}."


def mask_mobile(mobile: str | None) -> str:
    digits = re.sub(r"\D", "", mobile or "")
    return f"••••• {digits[-5:]}" if len(digits) >= 5 else ""


def winners_public(db: Session, day: m.DrawDay) -> list[dict]:
    """The ten Winners with prize, amount and the owner's masked name, in draw order."""
    numbers = [w["ticket"] for w in day.result.winners]
    owners = dict(
        db.execute(
            sa.select(m.Ticket.number, m.User)
            .join(m.Card, m.Ticket.card_id == m.Card.id)
            .join(m.Order, m.Card.order_id == m.Order.id)
            .join(m.User, m.Order.user_id == m.User.id)
            .where(m.Ticket.number.in_(numbers))
        ).all()
    )
    out = []
    for w in day.result.winners:
        label, amount = prize(w["rank"])
        owner = owners.get(w["ticket"])
        out.append(
            {
                **w,
                "label": label,
                "amount": amount,
                "name": mask_name(owner.name) if owner else "Boche member",
                "mobile": mask_mobile(owner.mobile) if owner else "",
            }
        )
    return out


def result_json(db: Session, day: m.DrawDay) -> dict:
    """Everything an outsider needs to re-check the draw, in the shape verifier/verify.py reads."""
    r = day.result
    return {
        "scheme": SCHEME,
        "draw_day": day.label,
        "kind": day.kind,
        "ticket_count": day.ticket_count,
        "fingerprint": day.fingerprint,
        "seed": r.seed,
        "drand": {
            "chain_hash": CHAIN_HASH,
            "round": day.drand_round,
            "randomness": r.randomness,
            "signature": r.signature,
        },
        "seal_url": day.seal_url,
        "winners": winners_public(db, day),
        "drawn_at": day.drawn_at.isoformat(),
        "published_at": day.published_at.isoformat(),
    }
