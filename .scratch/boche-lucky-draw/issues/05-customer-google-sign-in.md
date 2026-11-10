# 05: Customer signs in with Google

**What to build:** A Customer taps "Continue with Google" on the welcome screen (styled to match the theme) and lands on Home with their Google name and email. The mobile OTP, SIM check, new-phone and name screens are skipped. The session survives reloads, and signing out ends it.

**Blocked by:** 04

**Status:** ready-for-agent

- [ ] The welcome screen's phone field is replaced by a theme-aligned Google button; no other visual changes
- [ ] The server verifies the Google ID token (signature, audience, expiry) and creates or updates the Customer
- [ ] A signed httpOnly SameSite=Lax session cookie; current-user and sign-out endpoints
- [ ] The frontend fills the signed-in member's details from the current-user endpoint
- [ ] Tests: a valid token creates a session; invalid, expired and wrong-audience tokens are refused; the current-user endpoint without a session returns 401
