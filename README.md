# Boche Lucky Draw

The Boche prototype app with a backend, a database and a lucky-draw engine that outsiders can verify. The full README (setup, running a Test day, running the Verifier and assumptions) comes in ticket 15.

## Run locally

Needs Python 3.11+, a MySQL 8 server and Node (only for one frontend test).

1. Create the databases (in MySQL Workbench or the `mysql` client, as root):

   ```sql
   CREATE DATABASE boche CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;
   CREATE DATABASE boche_test CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;
   CREATE USER 'boche'@'localhost' IDENTIFIED BY '<password>';
   GRANT ALL PRIVILEGES ON boche.* TO 'boche'@'localhost';
   GRANT ALL PRIVILEGES ON boche_test.* TO 'boche'@'localhost';
   ```

2. Create `.env` in the repo root (it is git-ignored):

   ```
   DATABASE_URL=mysql+pymysql://boche:<password>@127.0.0.1:3306/boche
   TEST_DATABASE_URL=mysql+pymysql://boche:<password>@127.0.0.1:3306/boche_test
   GOOGLE_CLIENT_ID=<your OAuth web client id>.apps.googleusercontent.com
   ADMIN_EMAILS=you@gmail.com
   SESSION_SECRET=<any random string of 32+ characters>
   COOKIE_SECURE=false
   FOUNDER_MOBILE=           # pending: until set, the Founder's OTP is written to the server log
   ```

   The Google client must list `http://localhost` and `http://localhost:8000` as authorised JavaScript origins. Open the app at `http://localhost:8000`, not `127.0.0.1`.

3. Install, migrate and run:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python -m pip install -r backend\requirements-dev.txt
   .\.venv\Scripts\python -m alembic -c backend\alembic.ini upgrade head
   .\.venv\Scripts\python -m uvicorn app.main:app --app-dir backend --reload --port 8000
   ```

Open http://localhost:8000. The API lives under `/api`, and `/api/health` reports whether the database is connected.

## Tests and lint

```powershell
.\.venv\Scripts\python -m pytest              # all offline tests (DB tests use TEST_DATABASE_URL)
.\.venv\Scripts\python -m pytest -m network   # also hit the real drand network
.\.venv\Scripts\python -m ruff check .
```

The DB tests refuse to run unless the test database's name ends in `_test`, because they drop and recreate its tables.

## Hosting (Render + TiDB Cloud Starter)

`render.yaml` defines one free web service. In the Render dashboard, set `DATABASE_URL` to the TiDB connection string over TLS:

```
mysql+pymysql://<user>:<password>@<host>:4000/boche?ssl_ca=/etc/ssl/certs/ca-certificates.crt&ssl_verify_cert=true&ssl_verify_identity=true
```

## Layout

| Folder | Contents |
|---|---|
| `frontend/` | The prototype, served by the backend (changes are listed in the design note) |
| `backend/` | FastAPI app (`/api`), models, Alembic migrations |
| `engine/` | Draw engine: pure Python, standard library only |
| `verifier/` | Standalone Verifier for outsiders (see `verifier/README.md`) |
| `docs/` | ADRs and agent docs; design note later |
