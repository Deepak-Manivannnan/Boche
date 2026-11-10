# The Founder's OTP starts the draw, but the draw's inputs are fixed when Entries close

The client asked that the draw only runs after an Admin enters the OTP sent to the Founder. The brief also requires that nobody can influence the Winners or keep re-running until a friend wins. We reconcile both: the OTP decides only *when* the Draw run happens, never *what* it produces. When Entries close at 8:00 PM, the Ticket list, its Fingerprint and the Randomness round (released at 8:15 PM) are fixed and published in the Seal. A Draw run uses nothing else, so an OTP entered at 8:16 PM or 11 PM gives the same Winners. An OTP is refused before Entries close or before the Randomness round is released, a second Draw run returns the saved result, and the system has no action that redraws, edits or rejects Winners.

## Considered Options

- **Draw runs automatically at 8:15 PM; OTP only publishes** (the brief's literal wording): rejected because the client explicitly asked for OTP-before-draw.
- **OTP starts the draw with randomness taken at that moment**: rejected; the Admin could pick the moment and retry until a favoured result appeared.

## Consequences

- Withholding the OTP can delay the official result, but cannot hide it: anyone with the Seal and the Randomness round can compute the Winners with the Verifier.
- The Admin sees the Winners between the Draw run and Publish; this is a known, documented limitation.
