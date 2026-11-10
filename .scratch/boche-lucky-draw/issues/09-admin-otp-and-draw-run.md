# 09: Admin enters the Founder's OTP and the draw runs once

**What to build:** An approved Admin signs in with Google on the existing staff sign-in screen and opens a new "Tonight's draw" screen in the staff module's style. It shows status, Ticket count, Fingerprint and the Seal link. The Admin requests an OTP for the Founder, enters it, and the engine runs with only the sealed inputs. The ten Winners are saved and shown to the Admin. Retrying gives the same result.

**Blocked by:** 08

**Status:** done (two items pending, see below)

- [x] The staff sign-in screen uses a theme-aligned Google button; only emails on the server-side Admin list get in; existing staff venue screens are unchanged
- [x] OTP: 6 digits, stored hashed, 5-minute expiry, at most 5 wrong attempts, one active code per Draw day, cooldown between requests
- [x] The OTP message names the Draw day, Ticket count and Fingerprint prefix; sending goes through one interface with a development implementation that logs the code
- [x] OTP refused before the Draw day is sealed and its Randomness round is released
- [x] On a correct OTP: fetch the Randomness round, run the engine, save the result and a hash-chained run-log entry in one transaction; a repeat returns the saved result
- [x] No redraw, edit or reject operation exists
- [x] Tests: early OTP refused; wrong-OTP lockout; expiry; non-Admin refused; repeat run identical; simulated crash mid-run then restart gives the same Winners; message content

## Pending (waiting on the client)

- [ ] **Client's OTP service.** Plug it into the sender interface (send(to, text) in backend/app/otp.py). Until then `LogOtpSender` writes the SMS to the server log (Render -> Logs).
- [ ] **Founder's mobile number.** Set `FOUNDER_MOBILE` in .env and in the Render dashboard. Until then the log line says the number is not configured.

## Comments

- Admins sign in with Google on the staff sign-in screen (#/staff); the venue staff demo sign-in stays below it.
- Admin rights are re-checked against ADMIN_EMAILS on every request.
- Admin API: list/get draw days, request OTP, enter OTP to run. No redraw, edit or reject endpoint (tested).
- A failed run (drand down, crash) saves nothing, keeps the OTP valid, and is logged as `failed` in the hash-chained run log.
