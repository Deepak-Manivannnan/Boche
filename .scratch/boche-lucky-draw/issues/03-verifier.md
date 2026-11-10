# 03: Verifier checks a Draw day from its files, Seal and Randomness round

**What to build:** A standalone Verifier that needs only Python. It is given a Draw day's Ticket list, result, Seal and Randomness round, and reports pass or fail for each check: the list matches the Seal's Fingerprint, the randomness matches drand, and the recomputed Winners match the published Winners. It works offline from files first, then fetches the Randomness round from drand relays directly.

**Blocked by:** 02

**Status:** done

- [x] Runs with only the Python standard library; carries its own copy of the engine logic
- [x] A test keeps the Verifier's engine logic identical to the backend engine (shared known-answer vector)
- [x] Each failure names the exact step that failed
- [x] Fetches the Randomness round from at least two drand relays, checks the randomness is SHA-256 of the signature, and cross-checks the relays
- [x] Tests with fixtures: valid draw passes; tampered list, tampered Winner and wrong Randomness round each fail at the right step
- [x] Documents that full BLS signature checking is optional and not included
