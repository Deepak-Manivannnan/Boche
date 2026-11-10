# 02: Draw engine picks ten fair, reproducible Winners

**What to build:** A pure, standard-library-only draw engine. Given a Draw day's Tickets, a Randomness round value and the Draw day, it produces the canonical Ticket list, its Fingerprint and ten ranked Winners (three Main prizes, seven Consolation prizes). The same inputs always give the same Winners, and every Ticket has an equal chance. Built test-first.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] Canonical Ticket list: sorted, fixed header, `\n` endings, UTF-8; Fingerprint is SHA-256 of it
- [ ] Seed derived from Randomness round value, Fingerprint and Draw day
- [ ] Rejection sampling gives unbiased indices; ten distinct Winners; ranks 1–3 Main, 4–10 Consolation
- [ ] Fewer than ten Tickets raises a clear error
- [ ] Tests: same inputs give the same output; a fixed known-answer vector; one changed Ticket changes the Fingerprint; chi-square uniformity; 3 Tickets win about 3× as often as 1; 100,000 Tickets in under 2 s
- [ ] A command-line demo prints the Winners and the time taken for a generated 100,000-Ticket list
