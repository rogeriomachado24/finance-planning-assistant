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
- [ ] Database, services and REST API
- [ ] Vue dashboard
- [ ] LangGraph chat (Ollama / mock)

## Backend quick start

Requires Python 3.12+.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
```

On macOS/Linux use `.venv/bin/python` instead.
