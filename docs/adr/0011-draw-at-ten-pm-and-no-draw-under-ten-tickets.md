# The daily draw moves to 10 PM, and a day with fewer than 10 Tickets is not drawn

The draw is demonstrated live in the evening. Skip, Reset entries and Delete only work while today's Entries are still open, so with the 8 PM close a presenter could not run demo draws after 8 PM. The client moved the whole schedule two hours later. This changes the times in ADR-0001, 0002, 0005, 0008 and 0009; nothing else in them changes.

| IST | Step |
|---|---|
| until 10:00 PM | Entries open; an Admin can Skip, Reset entries and Delete today's draw |
| 10:00 PM | Entries close; the Ticket list is sealed and its Seal committed to GitHub |
| from 10:15 PM | the Randomness round is out; the Founder's OTP can be sent and the draw run (ADR-0001) |
| 10:30 PM | results go public (or straight after the Draw run, if later) |

The scheduled pings (`.github/workflows/tick.yml`) move with it. The whole window stays before midnight IST, so a Draw day never spans two dates.

## Fewer than 10 Tickets: no draw, the cards move on

A draw needs at least 10 Tickets, one per Winner. Before this, a day that closed with 1 to 9 was still sealed and its Seal published, but the draw could never run: the day stayed "sealed" for ever, its cards were stuck in it and their orders could never be refunded.

Now, when a real day's Entries close with fewer than 10 issued Tickets:

- Nothing is sealed and nothing goes to GitHub. The day becomes **carried** and is never drawn.
- Its entered cards (and their Tickets) move, still entered, into the next day taking Entries. Customers do nothing; their numbers show in the next day's draw.
- There an Admin can still **Reset entries** to give the cards back to their owners, and the orders can be refunded as for any open day.
- The run log records a `carried-over` entry with where the cards went and how many.
- A day with no Tickets at all is carried the same way (with nothing to move). If nobody entered, no day exists and nothing happens.

Test days are closed by an Admin, so instead **Close entries now** needs at least 10 Tickets.

## Consequences

- A carried day has no Seal, so the Verify page does not list it; the customer's Lucky Draw page says there was no draw that day.
- A Ticket can now be in a later day than the one its card was first entered into. Tickets stay unique across all time, so this never makes two days share a number.
- `draw_days.status` gains the value `carried` (migration 0007).
