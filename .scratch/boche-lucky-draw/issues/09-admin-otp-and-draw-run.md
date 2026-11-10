# 09: Admin enters the Founder's OTP and the draw runs once

**What to build:** An approved Admin signs in with Google on the existing staff sign-in screen and opens a new "Tonight's draw" screen in the staff module's style. It shows status, Ticket count, Fingerprint and the Seal link. The Admin requests an OTP for the Founder, enters it, and the engine runs with only the sealed inputs. The ten Winners are saved and shown to the Admin. Retrying gives the same result.

**Blocked by:** 08

**Status:** ready-for-agent

- [ ] The staff sign-in screen uses a theme-aligned Google button; only emails on the server-side Admin list get in; existing staff venue screens are unchanged
- [ ] OTP: 6 digits, stored hashed, 5-minute expiry, at most 5 wrong attempts, one active code per Draw day, cooldown between requests
- [ ] The OTP message names the Draw day, Ticket count and Fingerprint prefix; sending goes through one interface with a development implementation that logs the code
- [ ] OTP refused before the Draw day is sealed and its Randomness round is released
- [ ] On a correct OTP: fetch the Randomness round, run the engine, save the result and a hash-chained run-log entry in one transaction; a repeat returns the saved result
- [ ] No redraw, edit or reject operation exists
- [ ] Tests: early OTP refused; wrong-OTP lockout; expiry; non-Admin refused; repeat run identical; simulated crash mid-run then restart gives the same Winners; message content
