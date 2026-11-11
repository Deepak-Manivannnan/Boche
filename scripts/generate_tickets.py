"""Generate test Tickets for a realistic draw (at least 15,000 by default).

    python scripts/generate_tickets.py                     # new Test day with 15,000 tickets
    python scripts/generate_tickets.py --count 20000       # more tickets
    python scripts/generate_tickets.py --day test-…        # add to an existing open Test day
    python scripts/generate_tickets.py --close             # also close entries (seal) at the end

Tickets go through the same path as a real purchase: a priced Order, a signed mock-payment confirmation,
then server-generated lucky numbers. They are entered into a Test day, never a real Draw day. Uses
DATABASE_URL (from .env locally). The rest of the day (Founder OTP, draw, publish) is run from the
admin screen (#/staff -> Tonight's draw), or by the review demo."""

import argparse
import sys
import time
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import sqlalchemy as sa  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.core.clock import SystemClock  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.draw.testmode import close_test_day, create_test_day, seed_tickets  # noqa: E402

BATCH = 2500


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--count", type=int, default=15000, help="tickets to add (default 15000)")
    parser.add_argument("--day", help="label of an existing open Test day (default: create a new one)")
    parser.add_argument("--close", action="store_true", help="close entries and seal the list when done")
    args = parser.parse_args()
    if args.count < 1:
        parser.error("--count must be at least 1")

    settings, clock = Settings.from_env(), SystemClock()
    sessions = sessionmaker(
        sa.create_engine(settings.database_url, pool_pre_ping=True), expire_on_commit=False
    )
    with sessions() as db:
        label = args.day or create_test_day(db, clock.now()).label
    print(f"Test day {label}: adding {args.count:,} tickets")

    start, added, total = time.perf_counter(), 0, 0
    while added < args.count:
        step = min(BATCH, args.count - added)
        with sessions() as db:
            total = seed_tickets(db, label, step, clock.now(), settings.payment_secret)
        added += step
        print(f"  {added:,} / {args.count:,}  (day now holds {total:,})", flush=True)
    print(f"Done in {time.perf_counter() - start:.1f}s")

    if args.close:
        with sessions() as db:
            day = close_test_day(db, label, clock.now(), timedelta(0))
            print(
                f"Closed: {day.ticket_count:,} tickets, fingerprint {day.fingerprint}, "
                f"drand round {day.drand_round}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
