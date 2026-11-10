# 11: Public verify page and Verifier against the live site

**What to build:** A public, theme-aligned verify page lists Draw days. For each one it links the Ticket list CSV, the result, the Seal on GitHub and the drand Randomness round, and offers the Verifier download with a three-line guide. The Verifier checks any past Draw day against the hosted site by default.

**Blocked by:** 03, 10

**Status:** ready-for-agent

- [ ] The verify page is reachable without signing in and matches the existing theme
- [ ] Each Draw day shows Ticket count, Fingerprint, Randomness round and links to every file
- [ ] The Verifier defaults to the hosted base URL and the public seals repository
- [ ] The results screen's "Verify this draw" link opens this page
- [ ] Test: end-to-end Verifier run against a locally started server passes all checks
