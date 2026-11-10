# 12: Test mode runs a full Draw day on demand

**What to build:** An Admin opens Test mode and creates a Test day, seeds 15,000 Tickets through the real issuing path, closes Entries now, runs the real OTP step and sees the result published after a configurable gap. Test days are labelled TEST everywhere and never touch real Draw days. A script can also generate the Tickets from the command line.

**Blocked by:** 11

**Status:** done

- [x] The ticket generator script creates at least 15,000 Tickets via mock-paid Orders, from the command line or the Admin panel
- [x] "Close now" seals the Test day using the next available Randomness round (about 3 s later)
- [x] The OTP step and Draw run are the same as on a real Draw day; the gap before Publish is configurable (default 0)
- [x] Test days are visibly labelled TEST on every screen, page and Seal
- [x] Tests: real Draw days are unaffected by Test day actions; a full Test day flow ends with a result the Verifier accepts

## Comments

- Closing a Test day names a drand round at least 30 s ahead (same rule as a late real seal), not 3 s.
- On Test days only, the OTP is returned to the admin screen (`testCode`); real days never show it.
- Seeding is capped at 5,000 tickets per request; the UI adds 15,000 in batches of 2,500. Local MySQL: 15,000 in about 16 s.
- Live check on 2026-11-10: a 15,000-ticket test day sealed to the real GitHub repo, drawn with real drand round 33842545, and verified with all checks passing.
