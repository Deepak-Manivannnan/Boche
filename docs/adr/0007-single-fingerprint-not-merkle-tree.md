# A single SHA-256 Fingerprint of a public Ticket list, not a Merkle tree

Because the whole Ticket list for a Draw day is published as a CSV (Ticket numbers only, no customer data), any Customer can confirm their own Ticket is included by looking it up directly, and anyone can recompute one SHA-256 hash over the file to compare with the Seal. A Merkle tree would only add value if the list were kept private and Customers needed individual inclusion proofs; that extra code and explanation buys nothing here.

## Consequences

- The list's layout must be canonical (fixed ordering, line endings and encoding) so every machine computes the same Fingerprint.
- If the list ever has to become private, this decision should be revisited in favour of a Merkle tree.
