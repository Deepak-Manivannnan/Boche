# 04: Database schema and first public deploy

**What to build:** The app runs at a public Render URL with a connected TiDB database. The schema for all draw entities exists, and the server has an IST clock that tests can control. The prototype loads from the public link, and the service worker no longer caches API responses.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] Migrations create users (with role), orders, order_items, payments, cards, tickets (unique per Draw day and number), draw_days, draw_results (one per Draw day), draw_runs (append-only, hash-chained), otp_challenges, claims
- [ ] Database connection uses TLS; all secrets come from environment variables
- [ ] An injectable IST clock is used everywhere the server needs the time
- [ ] The service worker skips `/api` requests and its cache name is bumped
- [ ] Render deployment configuration is committed; the health endpoint reports the database as connected
- [ ] Tests: migrations apply cleanly; unique constraints reject duplicates
