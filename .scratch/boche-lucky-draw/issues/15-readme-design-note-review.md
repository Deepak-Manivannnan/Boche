# 15: README, design note and final review

**What to build:** Documents that let reviewers set up, run a Test day and verify a draw, plus a design note of at most two pages explaining how the Winners are picked, why nobody can rig the draw, how an outsider verifies it, and which threats it does and does not stop. Finish with a review of the code against this spec.

**Blocked by:** 13, 14

**Status:** ready-for-agent

- [ ] README: setup, environment variables, running a Test day, running the Verifier, and assumptions (Pack rule, OTP starts the draw per client instruction, Publish timing, mock payment, Founder without a login)
- [ ] Design note (at most two pages) with a threat table covering outside attacker, dishonest insider, fake entries, re-running, tampering in transit and approval misuse, each marked stopped, partly stopped or not stopped
- [ ] Known limitations stated plainly: withholding the OTP delays the result; the Admin sees the Winners before Publish; Tickets can be changed before the Seal; a GitHub force-push is possible but visible; Ticket legitimacy depends on payment confirmation
- [ ] A code review against the spec, with findings fixed
- [ ] An outsider can follow the README from a clean clone
