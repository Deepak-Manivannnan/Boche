# The Seal is committed to a public GitHub repository; the full Ticket list stays on our site

When Entries close, the Ticket list (as a public CSV with no customer data) and later the result are published on Boche's own download page. Only the Seal (Draw day, Ticket count, Fingerprint, Randomness round, about 100 characters) is committed to a separate public GitHub repository. An insider who can edit our site could change both the CSV and a Fingerprint shown beside it, but cannot quietly change a Seal that GitHub has timestamped and that others may have cloned. The Verifier reads the CSV and result from our site, the Seal from GitHub and the Randomness round from drand.

## Considered Options

- **Seal on our own site only**: rejected; insiders could rewrite it without trace.
- **OpenTimestamps (anchoring in Bitcoin)**: stronger and fully trustless, but confirmation takes hours and adds complexity; recorded as a future upgrade.

## Consequences

- The repository owner could force-push to rewrite history. This would be visible to anyone who cloned or watched the repository, but it is not impossible; the design note says so plainly.
- The server needs a narrowly scoped token that can write only to the seals repository.
