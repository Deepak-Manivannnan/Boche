# 05: Customer signs in with Google

**What to build:** A Customer taps "Continue with Google" on the welcome screen (styled to match the theme) and lands on Home with their Google name and email. The mobile OTP, SIM check, new-phone and name screens are skipped. The session survives reloads, and signing out ends it.

**Blocked by:** 04

**Status:** done

- [x] The welcome screen's phone field is replaced by Google's own sign-in button (pill, outline, as Google's branding rules require) in a slot that keeps the sheet's spacing; no other visual changes
- [x] The server verifies the Google ID token (Google's signature, audience = our client ID, issuer, expiry, verified email) and creates or updates the Customer
- [x] A signed httpOnly SameSite=Lax session cookie (Secure on HTTPS), expiring after 7 days; current-user and sign-out endpoints
- [x] The frontend fills the signed-in member's name and email from the current-user endpoint; the old OTP screen is no longer a way in
- [x] Tests: a valid token creates a session; invalid, expired, wrong-audience, wrong-issuer, foreign-signed and unverified-email tokens are refused; Google unreachable gives 503; the current-user endpoint without a session, with a tampered cookie or after 7 days returns 401

## Comments

- Emails on `ADMIN_EMAILS` get the `admin` role at sign-in. What an Admin can do is ticket 09.
- The member's mobile number is still the prototype's demo number on screens; Google does not supply one.
