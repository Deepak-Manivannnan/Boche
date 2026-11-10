# 08: Entries close and the Seal is published

**What to build:** At 8:00 PM IST, or as soon as the server next wakes after that, the Draw day closes. Its canonical Ticket list is frozen and downloadable as a public CSV, the Fingerprint is computed, the Randomness round for 8:15 PM is chosen, and the Seal is committed to the public GitHub seals repository.

**Blocked by:** 02, 07

**Status:** done

- [x] A lifecycle step runs on every request and on a tick endpoint, applies overdue steps, and is safe to repeat
- [x] The Ticket list CSV contains only position and Ticket number
- [x] The Randomness round for 20:15 IST is computed from drand quicknet's genesis time and period
- [x] The Seal (Draw day, Ticket count, Fingerprint, Randomness round) is committed via the GitHub API with a narrowly scoped token; failures are retried without changing the Seal; the commit link is stored
- [x] Tests (fake clock, fake GitHub): close is idempotent; late Entries refused; Seal contents correct; retry keeps the Fingerprint

## Comments

- A late seal names a round at least 30 s in the future and moves draw_not_before to its release (ADR-0002).
- A Seal already on GitHub is never overwritten; a different one raises SealConflict and is logged.
- Render needs SEALS_GITHUB_TOKEN set in the dashboard.
