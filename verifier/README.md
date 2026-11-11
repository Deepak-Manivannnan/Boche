# Boche Lucky Draw Verifier

`verify.py` lets anyone confirm that a past Draw day's Winners were not manipulated, without trusting Boche's servers. It is one file and needs only **Python 3.11 or newer**. There is nothing to install.

## Run it

```bash
python verify.py 2026-11-10
```

This downloads everything it needs and prints a check-by-check report. It exits with code `0` if the draw is verified and `1` if any check fails.

To check files you saved yourself (for example, downloaded from the Boche verify page), put `tickets.csv`, `result.json` and `seal.json` in one folder:

```bash
python verify.py 2026-11-10 --from-dir ./2026-11-10
```

If the folder also holds `drand.json`, the randomness is read from it. Otherwise it is fetched live from drand's public relays.

Options: `--site URL` (default `https://boche.onrender.com`) and `--seals-repo owner/repo` (default `Deepak-Manivannnan/boche-draw-seals`, the public GitHub repository of Seals).

You can also download `verify.py` from the app's **Verify the draw** page (`https://boche.onrender.com/verify-draw`), which lists every closed Draw day with its files, its Seal on GitHub and its drand round.

## What it checks

| Check | Evidence it uses | What a failure means |
|---|---|---|
| Seal | The Seal file | Wrong day, unknown algorithm or a different drand chain |
| Seal on GitHub | GitHub's commit history for the Seal file | The Seal was written after the randomness was public, or it was edited |
| Ticket list | SHA-256 of the downloaded `tickets.csv` against the Seal's Fingerprint | A Ticket was added, removed or changed after Entries closed |
| Randomness timing | drand's fixed schedule (genesis time + 3 s per round) | The Seal named a round whose value was already public |
| Randomness value | The round fetched from **at least two** independent drand relays | The result used randomness drand never produced |
| Winners | This script's own copy of the draw algorithm | The published Winners are not what the algorithm picks |

## The algorithm (boche-draw-v1)

1. **Ticket list:** sort the Ticket numbers and write `position,ticket_number` rows numbered from 1, with `\n` line endings, in UTF-8. The **Fingerprint** is the SHA-256 of these bytes.
2. **Seed:** `SHA-256("boche-draw-v1|<randomness>|<fingerprint>|<draw day>")`
3. **Pick *k*** (for *k* = 1 to 10): hash `seed + "|pick:k|try:t"` for t = 0, 1, … to get a 256-bit number. Reject numbers at or above the largest multiple of the remaining Ticket count (this removes modulo bias). Take the first accepted number modulo the remaining count as an index into the remaining list, and remove that Ticket.
4. **Prizes:** picks 1–3 win Main prizes; picks 4–10 win Consolation prizes.

The Boche backend runs exactly this code. A shared known-answer vector (`engine/tests/known_answer_v1.json`) and a parity test keep the two copies identical.

## Limits

- **drand's BLS signature is not checked.** The script checks that the randomness is the SHA-256 of drand's signature and that several independent relays return the same value. Fully verifying the BLS signature against drand's public key needs a pairing-crypto library, which would break the "nothing to install" rule. Anyone who wants that extra assurance can verify the round with drand's own client (`drand-client`) or any BLS12-381 library.
- **Offline mode can't check when the Seal was published.** Without network access, look at the Seal file's commit history on GitHub yourself.
- **Tickets added before Entries closed can't be told apart from genuine ones.** The Verifier proves the list did not change after it was sealed. It cannot prove every Ticket on the list was paid for. The design note covers that threat separately.
