# 14: Production hardening on the hosted app

**What to build:** The hosted app runs the full real-day flow reliably from the public link, from Google sign-in through Founder OTP to published results. The steps fire on time even after the free host has slept.

**Blocked by:** 12

**Status:** ready-for-agent

- [ ] Production environment configured: Google client, session secret, database TLS, GitHub seals token, payment HMAC key, Admin list, Founder mobile
- [ ] Google OAuth allowed origins include the hosted URL
- [ ] Rate limits on sign-in, OTP and Entry endpoints; security headers set
- [ ] External scheduled pings hit the tick endpoint at 20:00, 20:15 and 20:30 IST
- [ ] The client's OTP service is plugged into the sender interface once its details arrive
- [ ] A smoke-test script against the hosted URL passes
