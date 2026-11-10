"""The server's own Pack table and pricing. The browser only says which Packs and how many; every
price, tax and Ticket count comes from here (ADR-0006). A test keeps it identical to data.js.
Money is integer paise."""

from dataclasses import dataclass

LETTERS = "ABCDEFGHJKLMNPRSTUVWXYZ"  # lucky-number letters (no I, O, Q), as in the prototype
MAX_QTY = 10
TEA_GST_RATE = 5  # % on tea (HSN 0902)
LOGISTICS_GST_RATE = 18  # % on delivery


@dataclass(frozen=True)
class Pack:
    id: str
    size: str
    grams: int
    price_paise: int
    numbers: int  # lucky numbers (Tickets) on its Scratch card
    logistics_paise: int


PACKS = {
    "p250": Pack("p250", "250 g", 250, 9000, 1, 3600),
    "p500": Pack("p500", "500 g", 500, 17000, 3, 3600),
    "p1k": Pack("p1k", "1 kg", 1000, 32000, 8, 5200),
}


@dataclass(frozen=True)
class Quote:
    lines: tuple[tuple[Pack, int], ...]  # (pack, qty) in Pack table order, qty > 0
    subtotal_paise: int
    logistics_paise: int
    tea_gst_paise: int
    logistics_gst_paise: int
    gst_paise: int  # tea + logistics GST, rounded up to the next whole rupee
    total_paise: int

    @property
    def ticket_count(self) -> int:
        return sum(pack.numbers * qty for pack, qty in self.lines)


def _gst(paise: int, rate: int) -> int:
    """rate% of an amount, to the nearest paisa (halves round up, as the checkout screen does)."""
    return (paise * rate + 50) // 100


def quote(items: dict[str, int]) -> Quote:
    unknown = set(items) - set(PACKS)
    if unknown:
        raise ValueError(f"unknown pack(s): {', '.join(sorted(unknown))}")
    lines = tuple((pack, items[pid]) for pid, pack in PACKS.items() if items.get(pid, 0) > 0)
    if any(not 0 <= qty <= MAX_QTY for qty in items.values()):
        raise ValueError(f"each pack's quantity must be between 0 and {MAX_QTY}")
    if not lines:
        raise ValueError("the bag is empty")
    subtotal = sum(p.price_paise * q for p, q in lines)
    logistics = sum(p.logistics_paise * q for p, q in lines)
    tea_gst, log_gst = _gst(subtotal, TEA_GST_RATE), _gst(logistics, LOGISTICS_GST_RATE)
    gst = -(-(tea_gst + log_gst) // 100) * 100
    return Quote(lines, subtotal, logistics, tea_gst, log_gst, gst, subtotal + logistics + gst)
