# 11: Public verify page and Verifier against the live site

**What to build:** A public, theme-aligned verify page lists Draw days. For each one it links the Ticket list CSV, the result, the Seal on GitHub and the drand Randomness round, and offers the Verifier download with a three-line guide. The Verifier checks any past Draw day against the hosted site by default.

**Blocked by:** 03, 10

**Status:** done

- [x] The verify page is reachable without signing in and matches the existing theme
- [x] Each Draw day shows Ticket count, Fingerprint, Randomness round and links to every file
- [x] The Verifier defaults to the hosted base URL and the public seals repository
- [x] The results screen's "Verify this draw" link opens this page
- [x] Test: end-to-end Verifier run against a locally started server passes all checks

## Comments

- The page is `#/verify-draw` (`#/verify` was already the staff member-verification screen). Linked from the welcome screen ("Verify past draws") and under every winners list ("Verify this draw").
- The site serves the Verifier at /api/public/verifier/verify.py, byte for byte.
- Tested: the Verifier in online mode against the API passes; a Seal rewritten on GitHub fails provenance; an unpublished day fails as missing.
- Still to do once a real day is drawn on the hosted site: run `python verifier/verify.py <day>` against https://boche.onrender.com.
