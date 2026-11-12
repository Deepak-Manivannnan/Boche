# An Admin can close today's Entries early (Skip), so the draw runs without waiting for 8:15 PM

The client asked for a way to run the real daily draw straight away instead of waiting for the schedule. The Admin page offers **Skip the wait · draw now** on today's real Draw day while it is still taking Entries. It closes Entries at that moment and makes the Seal exactly as a late seal does (ADR-0002): the Seal names a drand round at least 30 seconds in the future. The Founder's OTP can be sent once that round is released, the draw runs as usual (ADR-0001), and the result is published straight after the Draw run instead of at 8:30 PM.

## Why this keeps the draw fair

- The Ticket list is still fixed and sealed before its Randomness round exists, so the Admin cannot see the randomness and then choose to skip.
- Skip only acts on a day that is still open. A day already sealed cannot be skipped, because its Randomness round is in the published Seal and is never changed. Between 8:00 and 8:15 PM the Admin still waits for the 8:15 round.
- Skip moves *when* the draw runs, never *what* it produces. There is still no action that redraws, edits or rejects Winners.

## Rules

- Only today's (IST) real Draw day can be skipped. Test days keep their own **Close entries now**, and tomorrow's day cannot be drawn today.
- The day needs at least 10 Tickets (one per Winner). Sealed with fewer, its draw could never run.
- Cards entered after a skip go into tomorrow's Draw day instead of being refused.
- A skip is irreversible, so the Admin page asks for a second tap. Each skip is written to the server log with the Admin's user id.

## Consequences

- Customers lose the rest of the day's entry window. Those who planned to enter before 8 PM are in tomorrow's draw instead.
- Customer pages show each day's actual results time (`publishNotBefore`) instead of a fixed 8:30 PM.
- The Seal format and the Verifier are unchanged. The Verifier already checks that the Seal was made before its round was released.
