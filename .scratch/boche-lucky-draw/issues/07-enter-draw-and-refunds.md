# 07: Entering the draw and refunds

**What to build:** "Enter today's Lucky Draw" saves the Entry on the server for the correct Draw day: today's before 8:00 PM IST, tomorrow's after. The Customer sees the status from the server. An Admin can refund an Order, following the agreed refund rules.

**Blocked by:** 06

**Status:** done

- [x] Entry assigns the Draw day by server IST time; a closed Draw day refuses Entries
- [x] A Customer can enter only their own Scratch cards, and each card only once
- [x] Refund before Entries close cancels the Order's Tickets; after close, refund waits until Publish; Orders with a Winner Ticket can't be refunded
- [x] The existing entry flow and statuses read from the API
- [x] Tests: 19:59:59 versus 20:00:00; no double Entry; another Customer's card refused; each refund rule

## Comments

- Refunds are an Admin API (POST /api/admin/orders/{id}/refund); there is no refund button yet.
- The prototype's draw hour in data.js is now 20 (8 PM), matching the server.
- Until ticket 10, the draw screen still shows the prototype's simulated winners, fed with real entries.
