# An Admin can delete today's completed draw and run it again

The app is a prototype that is demonstrated live: a presenter runs the whole flow (customers enter cards, the Admin skips the wait, the Founder's OTP, the reveal) several times in one sitting. Customers should still only ever see one draw per day, so instead of several draws a day the Admin page offers **Delete this draw** on today's real Draw day once it has been drawn. This changes ADR-0001's promise that "the system has no action that redraws": the client chose this, and chose to keep it always available rather than behind a demo-only setting.

## What Delete does

- Erases the day's Winners, their Claims, the Founder OTPs and the sealed Ticket list, and removes the day's Seal file from the GitHub seals repository.
- The day's entered cards go back to their owners, who can enter them again; nothing is refunded or removed from the Customer's orders.
- The day reopens empty with its normal schedule (closes at 8:00 PM), so it can be drawn again with Skip once it has 10 Tickets, or at 8:15 PM as usual.
- The hash-chained run log gets a `deleted` entry with the erased Fingerprint, Randomness round and Winners. The log is never edited.

## Rules

- Only today's (IST) real Draw day, only once it has been drawn, and only before 8:00 PM. Reopened after 8:00 PM, the day would close again at once with no Tickets and could never be drawn.
- If the Seal cannot be removed from GitHub, nothing is deleted.
- Two taps on the Admin page, as for Skip.

## Consequences

- An Admin can now delete a result and draw again, so the "nobody can re-run until a friend wins" guarantee no longer holds against Admins. It still holds against everyone else, and every delete is recorded. If the app ever runs real paid draws, this should be put behind a setting or removed.
- The Seal's GitHub history keeps every version. For a day that was deleted and drawn again, the Verifier's Seal check reports the Seal as edited (more than one revision), while the Ticket list, Randomness and Winners checks still pass. This is the intended, public trace of a deleted draw.
- Customers' Lucky Draw page shows the countdown again after a delete, and plays the reveal for the new Winners when they are published.
