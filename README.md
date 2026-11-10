# Boche Lucky Draw

The Boche prototype app with a backend, a database and a lucky-draw engine that outsiders can verify. The full README (setup, running a Test day, running the Verifier and assumptions) comes in ticket 15.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend\requirements-dev.txt
.\.venv\Scripts\python -m uvicorn app.main:app --app-dir backend --reload --port 8000
```

Open http://localhost:8000. The API lives under `/api` (for example `/api/health`).

## Tests and lint

```powershell
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m ruff check .
```

## Layout

| Folder | Contents |
|---|---|
| `frontend/` | The prototype, unchanged, served by the backend |
| `backend/` | FastAPI app (`/api`) |
| `engine/` | Draw engine: pure Python, standard library only |
| `verifier/` | Standalone Verifier for outsiders |
| `docs/` | ADRs and agent docs; design note later |
