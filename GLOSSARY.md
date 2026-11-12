# Boche Lucky Draw

The daily lucky draw attached to Boche Tea purchases: customers earn tickets by buying tea, enter them into a draw day, and ten tickets win prizes in a draw that outsiders can check.

## People

**Customer**:
A person who signs in to the Boche app, buys tea and takes part in the lucky draw.
_Avoid_: User, member (in draw contexts), player

**Admin**:
A Boche back-office person, on an approved list, who requests and enters the Founder's OTP to run a draw day's draw.
_Avoid_: Staff, operator, owner

**Founder**:
The person who receives the OTP on their own mobile and passes it to the Admin; their OTP is the approval needed to run the draw. Has no login.
_Avoid_: Owner, approver, admin

## Buying and tickets

**Pack**:
A sellable size of Boche Tea (250 g, 500 g or 1 kg) with a fixed price and a fixed number of lucky numbers.
_Avoid_: Product, SKU, item

**Order**:
One paid purchase of one or more Packs by a Customer.
_Avoid_: Purchase, transaction, bill

**Scratch card**:
The card a Customer receives for each Pack in an Order; it hides that Pack's lucky numbers until scratched.
_Avoid_: Coupon, voucher

**Ticket**:
One lucky number, unique within its draw day, that has one equal chance of winning. A Ticket exists only after its Order's payment is confirmed.
_Avoid_: Coupon, entry, number (alone)

**Lucky number**:
The printed form of a Ticket, two letters and six digits (e.g. "AB 123456").
_Avoid_: Coupon code

**Entry**:
A Customer's act of putting a Scratch card's Tickets into a draw day.
_Avoid_: Submission, registration

**Refund**:
Cancelling a paid Order; it removes that Order's Tickets from any draw day that has not yet closed.

## The draw day

**Draw day**:
One calendar day's draw, from accepting Entries through to published results. Either real or a Test day.
_Avoid_: Contest, round (use Randomness round for drand)

**Test day**:
A Draw day created on demand by an Admin to rehearse the full cycle; it never mixes with real Draw days.
_Avoid_: Demo, sandbox

**Entries close**:
The moment (8:00 PM IST on a real Draw day, or earlier if an Admin uses **Skip**) after which no Ticket can be added, removed or changed for that day.

**Skip**:
An Admin closing today's Entries early so its draw runs without waiting for 8:15 PM (ADR-0008). The Seal then names a Randomness round about 30 seconds ahead, and the result is published straight after the Draw run.
_Avoid_: Fast-forward, instant draw
_Avoid_: Cut-off, lock

**Seal**:
A small public record, made when Entries close, naming the Draw day, its Ticket count, its Fingerprint and its Randomness round.
_Avoid_: Commitment (in user-facing text), snapshot

**Fingerprint**:
The SHA-256 hash of the Draw day's published Ticket list; any change to the list gives a different Fingerprint.
_Avoid_: Checksum, signature, root

**Randomness round**:
The single numbered drand value, released at 8:15 PM IST and named in the Seal before it exists, that supplies the draw's randomness.
_Avoid_: Seed (the seed is derived from it), random number

**Delete (a draw)**:
An Admin erasing today's completed draw (Winners, Claims, sealed list and Seal) so the day reopens empty and can be drawn again (ADR-0009). Recorded in the run log and visible in the Seal's GitHub history.
_Avoid_: Reset, redraw

**Draw run**:
One execution of the draw for a Draw day. Every Draw run is logged; all Draw runs of a day give the same Winners.
_Avoid_: Re-draw, spin

**Winner**:
One of the ten Tickets picked by the draw. The first three picked win a **Main prize**; the next seven win a **Consolation prize**.
_Avoid_: Winning number, lucky winner

**Publish**:
Making a Draw day's Winners visible to Customers and the public (8:30 PM IST, or right after the Draw run if later).
_Avoid_: Release, announce, approve

## Checking and claiming

**Verifier**:
A small standalone program anyone can run, without access to Boche servers, to check a past Draw day against its Seal and Randomness round.
_Avoid_: Checker, auditor (the auditor is the person running it)

**Claim**:
A winning Customer's request to be paid the prize for a Winner Ticket.
_Avoid_: Redemption, payout request
