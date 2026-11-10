# 10: Results are published and Customers see their outcome

**What to build:** At 8:30 PM IST, or straight after the Draw run if that is later, the Winners become visible on the existing draw screen, 30-day calendar, My wins and Claim screens. Winners are masked. Each Customer sees, per Ticket, whether it was included in the sealed list and whether it won. The prototype's simulated draw and the customer "Demo: run today's draw now" button are removed.

**Blocked by:** 09

**Status:** done

- [x] Nothing about Winners is visible to Customers or the public before Publish
- [x] The public result shows masked Winners (first name and last initial, masked mobile), Fingerprint, Randomness round and Seal link
- [x] The per-Customer result gives included and won flags for each Ticket
- [x] Claims are stored on the server and allowed only for Winner Tickets
- [x] The prototype's simulated draw code and the demo run-now button are removed
- [x] Tests: no early visibility; masking; included/won flags; Claims refused for non-Winners

## Comments

- Publish happens at max(8:30 PM IST, Draw run); a run after 8:30 is published in the same request.
- Per card, /api/me/orders gives `included` (in the sealed list), `wins` (only after publish) and `claim`.
- Claims: POST /api/claims {cardId}; one Claim per winning Ticket, repeat returns the same claim.
- Removed the prototype's simulated draw (seeded RNG, 3,200-entry demo pool, forced demo wins) and the customer "Demo: run today's draw now" button.
- The draw screen counts down to 8:30 PM IST ("Results in") and then polls for the official result.
- A test runs the real Verifier on a full day's public files from the API.
