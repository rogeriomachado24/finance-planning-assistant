# Personal Finance Planning Assistant

A financial goal simulator with a conversational interface. Enter your current finances and a
goal ("€80,000 for a house deposit by June 2032"), see when you're projected to reach it, compare
scenarios, and ask what-if questions in plain English.

**Core principle:** all financial maths runs in a deterministic, tested Python engine. The LLM only
interprets questions and explains results; it never calculates or changes a number.

> This is a planning tool, not financial advice. Projections depend entirely on the assumptions
> you enter and are not guarantees.

## Status

Phase 1 in progress. See [docs/PHASE1_DESIGN.md](docs/PHASE1_DESIGN.md) for the financial model,
architecture and build order.

- [x] Design
- [x] Financial engine (`backend/app/domain`) with unit and property-based tests
- [x] Database, services and REST API, with demo data
- [ ] Vue dashboard (projection page done; forms and scenario comparison next)
- [ ] LangGraph chat (Ollama / mock)

## Backend quick start

Requires Python 3.12+.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest                        # run the tests
.\.venv\Scripts\python.exe -m app.seed                      # optional: load the demo plan
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload # start the API
```

Then open <http://127.0.0.1:8000/docs> to try every endpoint in the browser.

- The database is a SQLite file, `backend/finance.db`. It's created and migrated automatically
  when the server starts, with three editable assumption sets (conservative, base, optimistic).
- `app.seed` adds a sample person with a house-deposit goal. It refuses to overwrite data you
  entered yourself; `python -m app.seed --reset` deletes everything and reloads the demo.
- Set `DATABASE_URL` (or put it in `backend/.env`) to use a different database.

On macOS/Linux use `.venv/bin/python` instead.

## Frontend quick start

Requires Node.js 20+. Start the backend first (above), then:

```powershell
cd frontend
npm install
npm run dev      # http://localhost:5173 (calls to /api are forwarded to the backend)
npm test         # unit and component tests
npm run build    # type-check and production build
```

The frontend's TypeScript types are generated from the backend's OpenAPI description. After
changing the API: `python -m app.export_openapi` in `backend/`, then `npm run api:types` in
`frontend/`. A backend test fails if you forget the first step.
