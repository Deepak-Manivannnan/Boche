# 07: Entering the draw and refunds

**What to build:** "Enter today's Lucky Draw" saves the Entry on the server for the correct Draw day: today's before 8:00 PM IST, tomorrow's after. The Customer sees the status from the server. An Admin can refund an Order, following the agreed refund rules.

**Blocked by:** 06

**Status:** ready-for-agent

- [ ] Entry assigns the Draw day by server IST time; a closed Draw day refuses Entries
- [ ] A Customer can enter only their own Scratch cards, and each card only once
- [ ] Refund before Entries close cancels the Order's Tickets; after close, refund waits until Publish; Orders with a Winner Ticket can't be refunded
- [ ] The existing entry flow and statuses read from the API
- [ ] Tests: 19:59:59 versus 20:00:00; no double Entry; another Customer's card refused; each refund rule
