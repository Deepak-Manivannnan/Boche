# 04: Database schema and first public deploy

**What to build:** The app runs at a public Render URL with a connected TiDB database. The schema for all draw entities exists, and the server has an IST clock that tests can control. The prototype loads from the public link, and the service worker no longer caches API responses.

**Blocked by:** 01

**Status:** done

### 04a: local (done)
- [x] Migrations create users (with role), orders, order_items, payments, cards, tickets (lucky numbers unique), draw_days, draw_results (one per Draw day), draw_runs (append-only, hash-chain fields, unique sequence), otp_challenges, claims
- [x] All secrets come from environment variables (`.env` locally, git-ignored)
- [x] An injectable IST clock (system and fixed clocks, IST date and time helpers)
- [x] The service worker skips `/api` requests and its cache name is bumped (v130 → v131)
- [x] Render deployment configuration is committed (`render.yaml`); the health endpoint reports the database as connected, or 503 when it is not
- [x] Tests: migrations apply, roll back and reapply; migrations match the models exactly; unique constraints reject duplicates

### 04b: hosting (waiting on accounts)
- [x] TiDB Cloud Starter cluster created (Singapore, TiDB v8.5.3); `DATABASE_URL` uses TLS with certificate and hostname checks; migrations applied; all DB tests pass on TiDB
- [x] Code pushed to the GitHub repository`n- [x] Render service created from `render.yaml` (https://boche.onrender.com)
- [x] The public Render URL serves the prototype and `/api/health` reports the database as connected
