# 01: Monorepo layout and FastAPI skeleton serving the prototype

**What to build:** The prototype moves into its own frontend folder (in a commit of its own, so the move is easy to review). A minimal FastAPI backend serves those files and a health endpoint. Opening the app locally looks and behaves exactly as before.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] The prototype is moved into the frontend folder in a commit containing only the move
- [ ] The backend starts with one command and serves the prototype at `/`
- [ ] A health endpoint under `/api` returns ok
- [ ] Backend, engine and Verifier folders exist, with the Python toolchain (pytest, ruff) configured
- [ ] Tests: health endpoint responds; the index page is served
- [ ] Every prototype screen still works unchanged in the browser
