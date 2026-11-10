# drand quicknet is the draw's only source of randomness

The draw's randomness comes from one round of drand's quicknet beacon, run by the League of Entropy (independent organisations including Cloudflare, Protocol Labs and universities). A new round is released every 3 seconds, its value cannot be predicted or chosen by any single member, and anyone can fetch it from public relays and check it. Because round numbers follow from the chain's genesis time and period, the round for 8:15 PM IST is computed in advance and named in the Seal at 8:00 PM, before its value exists. No server-side random generator ever influences which Tickets win.

## Considered Options

- **Server-side secure RNG**: unverifiable by outsiders; insiders could re-roll in secret.
- **Commit-reveal server seed (casino "provably fair")**: outsiders can check, but the operator chooses the seed and could grind for a favourable one.
- **NIST Randomness Beacon**: also suitable; drand chosen for its multi-party operation and 3-second cadence (useful for test days).
- **Chainlink VRF**: needs a blockchain and fees; out of proportion for this system.

## Consequences

- If drand is unavailable when the Draw run is attempted, the run waits; the Randomness round named in the Seal is never changed.
- The Verifier fetches the round directly from drand relays, not from Boche.
