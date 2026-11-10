# 12: Test mode runs a full Draw day on demand

**What to build:** An Admin opens Test mode and creates a Test day, seeds 15,000 Tickets through the real issuing path, closes Entries now, runs the real OTP step and sees the result published after a configurable gap. Test days are labelled TEST everywhere and never touch real Draw days. A script can also generate the Tickets from the command line.

**Blocked by:** 11

**Status:** ready-for-agent

- [ ] The ticket generator script creates at least 15,000 Tickets via mock-paid Orders, from the command line or the Admin panel
- [ ] "Close now" seals the Test day using the next available Randomness round (about 3 s later)
- [ ] The OTP step and Draw run are the same as on a real Draw day; the gap before Publish is configurable (default 0)
- [ ] Test days are visibly labelled TEST on every screen, page and Seal
- [ ] Tests: real Draw days are unaffected by Test day actions; a full Test day flow ends with a result the Verifier accepts
