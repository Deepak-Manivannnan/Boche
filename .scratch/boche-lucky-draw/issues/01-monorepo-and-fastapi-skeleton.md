# 01: Monorepo layout and FastAPI skeleton serving the prototype

**What to build:** The prototype moves into its own frontend folder (in a commit of its own, so the move is easy to review). A minimal FastAPI backend serves those files and a health endpoint. Opening the app locally looks and behaves exactly as before.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] The prototype is moved into the frontend folder in a commit containing only the move
- [x] The backend starts with one command and serves the prototype at `/`
- [x] A health endpoint under `/api` returns ok
- [x] Backend, engine and Verifier folders exist, with the Python toolchain (pytest, ruff) configured
- [x] Tests: health endpoint responds; the index page is served
- [x] Every prototype screen still works unchanged in the browser
