# 06: Paid Orders issue server-generated Tickets

**What to build:** A Customer buys tea through the existing shop and UPI screens. The server prices the Order itself, the mock payment provider confirms payment with a signed message, and only then are Scratch cards and lucky numbers created. They show up in My orders, My lucky numbers and the scratch screen, and survive reloads.

**Blocked by:** 05

**Status:** done

- [x] The server computes price, GST, logistics and Ticket count from its own Pack table; values sent by the browser are ignored
- [x] The mock payment sends an HMAC-signed confirmation; Tickets are issued only after the signature is verified
- [x] Duplicate confirmations issue Tickets only once
- [x] Lucky numbers come from a secure random source, use the "XY 123456" format and are unique per Draw day
- [x] The existing order, numbers and scratch screens read from the API; scratching stays in the browser
- [x] Tests: bad signature refused; duplicate confirmation is idempotent; Ticket counts per Pack are correct; a client-sent price or count is ignored

## Comments

- Entering the draw and claiming are still remembered per device (cardLocal in app.js) until tickets 07 and 10 move them to the server.
- Orders created by the old browser-only prototype are no longer shown.
