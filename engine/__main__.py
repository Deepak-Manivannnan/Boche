"""Command-line demo: python -m engine demo --tickets 100000"""

import argparse
import hashlib
import time

from engine import pick_winners

LETTERS = "ABCDEFGHJKLMNPRSTUVWXYZ"  # the prototype's lucky-number letters


def demo_tickets(n: int) -> list[str]:
    return [f"{LETTERS[i % 23]}{LETTERS[i // 23 % 23]} {i:06d}" for i in range(n)]


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m engine")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="draw from a generated Ticket list and time it")
    demo.add_argument("--tickets", type=int, default=100_000)
    demo.add_argument("--day", default="2026-11-10")
    demo.add_argument("--randomness", help="hex value (default: a fixed demo value)")
    args = parser.parse_args()

    randomness = args.randomness or hashlib.sha256(b"demo randomness").hexdigest()
    pool = demo_tickets(args.tickets)
    start = time.perf_counter()
    result = pick_winners(pool, randomness, args.day)
    elapsed = time.perf_counter() - start

    print(f"Draw day     {result.draw_day}")
    print(f"Tickets      {len(pool):,}")
    print(f"Fingerprint  {result.fingerprint}")
    print(f"Randomness   {result.randomness}")
    print(f"Seed         {result.seed}")
    for w in result.winners:
        label = f"Main prize {w.rank}" if w.prize == "main" else f"Consolation {w.rank - 3}"
        print(f"  #{w.rank:<2} {label:<14} {w.ticket}  (position {w.position:,})")
    print(f"Drew in {elapsed:.3f}s")


if __name__ == "__main__":
    main()
