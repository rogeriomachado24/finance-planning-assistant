# Personal Finance Planning Assistant — Phase 1 Design

Phase 1 delivers a **Financial Goal Simulator with a conversational interface**: the user
describes their current finances and one goal, sees a projection, compares scenarios, and asks
"what if" questions in plain English.

## 1. Guiding principles

1. **Deterministic software does the maths. The LLM only interprets and explains.**
   Every number shown to the user comes from the Python domain layer. The LLM turns a
   question into structured parameters, triggers a calculation, and explains the result.
   It never computes, rounds or edits a figure.
2. **Assumptions are always visible.** Every projection carries the assumptions that produced
   it, and the UI shows them next to the result.
3. **Projections, not advice.** The app models scenarios the user defines. It never recommends
   products or presents assumed returns as guaranteed.
4. **Works without an LLM.** Dashboard, projections and scenarios are fully usable with no
   model available; the chat has a rule-based mock mode.
5. **Simple and explicit beats realistic and hidden.** Phase 1 prefers a small model with
   documented simplifications over a detailed model nobody can verify.

## 2. Scope

**In Phase 1:** one financial profile, one active goal, assumption set with
conservative/base/optimistic variants, monthly projection engine, scenario comparison,
REST API, Vue dashboard with charts, LangGraph chat backed by a switchable LLM provider
(Ollama by default).

**Not in Phase 1:** bank integrations, market data, recommendations, rebalancing, web research,
RAG/embeddings, scraping, mortgage APIs, Monte Carlo, authentication, multiple users or goals,
multi-agent systems, autonomous actions, debt interest, inflation-adjusted results.

## 3. Financial model

### 3.1 Inputs

| Group | Field | Notes |
|---|---|---|
| Profile (facts about today) | age | informational in Phase 1 |
| | monthly net income | grows with salary growth |
| | other monthly income | does **not** grow |
| | monthly expenses | excludes debt payments; grows with expense growth |
| | cash | earns 0% |
| | investments | grows at the assumed return |
| | monthly investment contribution | planned amount moved from cash to investments |
| | debt balance, monthly debt payment | no interest in Phase 1 |
| Assumptions (forward-looking rates) | annual return | e.g. `0.05` = 5% |
| | annual salary growth | |
| | annual expense growth | |
| | annual inflation | stored and displayed, not used in calculations |
| Goal | name, type, target amount, target date, description | target = amount to accumulate |

All rates are decimals (`0.07` = 7%). Rates must be greater than −100% and at most 100%;
anything larger is almost certainly a typo (`7` instead of `0.07`) and is rejected.

### 3.2 Conventions

| Topic | Convention |
|---|---|
| Period | Monthly. Month 0 is the opening position; month *k* is the end of the *k*-th month. |
| Start date | First day of the current month, passed in explicitly (no hidden clock). |
| Return conversion | `r_m = (1 + r_annual)^(1/12) − 1`, so 12 months compound to exactly the annual rate. |
| Salary / expense growth | Applied in **annual steps**: months 1–12 use today's values, months 13–24 are grown once, etc. |
| Contribution timing | End of month; it starts earning returns the following month. |
| Goal funding | **Liquid assets = cash + investments.** Debt does not reduce goal progress. |
| Currency | Nominal EUR. Floats in the engine, rounded to cents at the API boundary. |

Why floats rather than `Decimal`: this is a projection engine, not a ledger. Float64 error on
these magnitudes is around 10⁻¹⁰ €, many orders of magnitude below the uncertainty in any
assumed return. Floats keep the maths readable (exponents, bisection) and the tests exact enough.

### 3.3 Monthly algorithm

For each month *k* = 1 … N (with `y = (k − 1) // 12` completed years):

```
income_k        = net_income × (1 + salary_growth)^y + other_income
expenses_k      = expenses   × (1 + expense_growth)^y
debt_payment_k  = min(planned_debt_payment, debt_balance)
surplus_k       = income_k − expenses_k − debt_payment_k
debt_balance   −= debt_payment_k

investments    ×= (1 + r_m)                                   # growth on opening balance
available       = cash + surplus_k
contribution_k  = min(planned_contribution, max(available, 0))  # cannot invest money you don't have
cash            = available − contribution_k                   # leftover surplus stays in cash
if cash < 0:                                                   # negative surplus, cash exhausted
    withdrawal_k = min(−cash, investments)                     # sell investments to cover it
    investments −= withdrawal_k ; cash += withdrawal_k
investments    += contribution_k
```

If cash is still negative after that, the plan has an **unfunded deficit** and a warning is raised.
Once the debt is repaid, the payment stops and that money flows into the surplus.

The engine emits structured warnings (first month of occurrence): contribution reduced,
investments withdrawn, liquid funds exhausted, debt paid off.

### 3.4 Definitions

- **Monthly surplus** = net income + other income − expenses − debt payment
- **Savings rate** = surplus ÷ (net income + other income); undefined when income is 0
- **Net worth** = cash + investments − debt
- **Goal progress** = min(liquid assets ÷ target, 100%)
- **Goal date** = first month-end at which liquid assets ≥ target, searched up to 50 years;
  "not reachable" beyond that
- **Required monthly contribution** = the monthly amount that, invested at the assumed return
  from next month, brings today's cash + investments to the target by the target date:

  ```
  G = (1 + r_m)^n                      # growth factor over n months
  A = (G − 1) / r_m   (A = n if r_m = 0)   # future value of 1 € per month, ordinary annuity
  required = max(0, (target − cash − investments × G) / A)
  ```

  It answers "how much do I need to set aside each month?" independently of income. The app then
  compares it with the monthly surplus to show whether it's affordable.

  Implementation note: `G − 1` is computed as `expm1(n · log1p(r_m))`. For returns close to zero,
  the textbook `(1 + r)^n − 1` subtracts two nearly equal numbers and loses precision.
  The property-based tests caught this.

### 3.5 Stated simplifications

Shown to the user wherever projections appear:
no taxes on gains, no investment fees (net them into the return), no debt interest,
no inflation adjustment, salary growth applied to net income, constant rates, cash earns nothing.

## 4. Scenarios

A scenario is a **named set of overrides applied to the saved profile and assumptions**:

```json
{"name": "Higher contribution", "overrides": {"monthly_investment_contribution_delta": 100}}
```

Supported overrides: contribution, net income and expenses (each absolute or delta), annual
return, salary growth, expense growth. The chat produces exactly the same structure, so "what if I invest
€200 more per month?" becomes `{"monthly_investment_contribution_delta": 200}`.

Two separate dimensions:

- **Assumption sets:** conservative / base / optimistic (how pessimistic the rates are).
  Preset values are illustrative and editable.
- **Levers:** Current plan, Higher contribution (+€100/month), Higher income (+2 pp salary growth).

Scenario **definitions** are stored; **results** are always recomputed.

Each result contains: scenario name, effective assumptions, contribution, target amount and date,
projected goal date, months to goal, projected value at target date, whether the goal is reached,
shortfall, required monthly contribution, current surplus, warnings, and the monthly series used
by the chart.

## 5. Architecture

```
Vue (dashboard, chat)
   │  REST/JSON
FastAPI  (api/)          HTTP, request validation, OpenAPI
   │
Services (services/)     use cases: load profile, run scenarios, handle chat turn
   │            │
   │       Agent (agents/, tools/)   LangGraph workflow; tools call services
   │            │
Domain (domain/)         pure financial engine — no framework imports
   │
DB (db/)                 SQLAlchemy models + Alembic migrations, SQLite → Postgres-ready
```

**Dependency rule:** `domain` imports nothing from the rest of the app or from any framework.
Everything else may depend on `domain`, never the reverse.

```
backend/
├── app/
│   ├── domain/     # models, rates, cashflow, projection, goals, scenarios
│   ├── services/
│   ├── agents/     # LangGraph graph, state, prompts, LLM provider factory
│   ├── tools/      # tool schemas wrapping services
│   ├── db/
│   ├── schemas/    # Pydantic API models
│   ├── api/
│   └── main.py
├── tests/
└── pyproject.toml
frontend/            # Vue 3 + TypeScript + Vite + Tailwind
docs/
```

## 6. Conversational AI

One LangGraph graph with explicit state. There's no open-ended tool-calling loop: the LLM fills in a
structured request and Python decides what runs. This is more reliable with small local models
and fully testable.

```
parse_intent ─► validate ─► execute (no LLM) ─► explain ─► END
                   │
                   ├─► ask_clarification ─► END   (missing profile/goal, ambiguous amount)
                   └─► decline_unsupported ─► END (advice requests, out-of-scope questions)
```

- **Intents:** run projection, compare scenarios, what-if (overrides), required contribution,
  goal date, explain assumptions, unsupported. They're modelled as a Pydantic discriminated union.
- **Grounding:** `/chat` returns `{reply, results, assumptions}`. The UI renders figures from
  `results` as cards, and the LLM text is commentary around them. The explain prompt receives only
  the structured result and is told to use no other numbers.
- **Read-only:** what-ifs never modify the saved profile.
- **Memory:** in-memory LangGraph checkpointer keyed by `thread_id`, so follow-ups work
  ("and with €300 instead?").
- **Providers:** `LLM_PROVIDER=ollama | mock` (code default `mock`, so tests and CI never need a
  model; a local `.env` selects `ollama`; model set by `OLLAMA_MODEL`, currently `phi3`). A factory
  builds the provider; adding Gemini/OpenAI later is one branch.
- **Measured, not assumed:** `python -m app.agents.evaluate --model phi3` scores parsers on a
  labelled set (35 messages, some deliberately outside the rules' patterns). Result: rules 86%,
  phi3 alone 63%, rules first then phi3 89%. So the rules parse first and the model handles only
  messages the rules can't place; its output is checked (numbers must appear in the message) and
  rejected output falls back to the rules. Replies are templated by default: phi3's rewording
  produced wrong statements ("a month before" for 11 months, an invented date, two scenarios
  merged) that automated checks can't all catch.
- **Mock mode:** regex intent parser plus templated explanations. Used in CI and when no
  model is available.
- **Language rules:** "Under these assumptions…", "This scenario results in…",
  "This is a projection, not a guarantee." Never "you should buy…".

## 7. API

Interactive documentation at `/docs` (generated from the Pydantic schemas).

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | liveness + database check (LLM provider status added with the chat) |
| GET / PUT | `/profile` | read / create-or-replace the single profile; GET also returns today's position |
| GET / POST | `/goals` | list goals / create (the new goal becomes the active one) |
| GET | `/assumptions` | list assumption sets |
| PUT | `/assumptions/{name}` | create or replace one assumption set |
| POST | `/simulate` | projection of the stored plan, optional what-if overrides (never saved) |
| POST | `/scenarios/compare` | run several scenarios side by side (default: built-in, then saved); each comes with its difference from the first (baseline) scenario |
| GET / POST | `/scenarios` | list / save scenario definitions (same name replaces) |
| DELETE | `/scenarios/{id}` | delete a saved scenario |
| POST | `/chat` | one conversational turn (step 5) |

Errors: `404` when something the request needs isn't stored yet, `422` for invalid input.
Both carry a `detail` message; schema validation errors list the offending fields.
Money in responses is rounded to the cent (half up); the dates are ISO (`2032-06-01`) and the UI
formats them.

## 8. Data model

`FinancialProfile`, `Goal` (with `is_active`), `AssumptionSet` (name, rates),
`Scenario` (name, overrides as JSON). SQLAlchemy 2.0 with Alembic migrations from the start.
Money columns use `Numeric`. No user table in Phase 1.

## 9. Testing

- **Domain unit tests:** every case in the Phase 1 brief (compound growth, contributions, zero return,
  no contribution, invalid values, goal already reached, unreachable goal, salary and expense growth,
  required contribution, goal date), plus debt payoff and cash-deficit handling.
- **Reference tests:** with constant rates and enough surplus, the simulator must match the
  closed-form annuity formulas.
- **Property-based tests (Hypothesis):** higher contribution never lowers liquid assets (for
  non-negative returns); higher return never lowers them; the required contribution fed back into
  the simulator reaches the target at the target date.
- **API integration tests** against a temporary SQLite database.
- **Graph tests** with the mock provider (intent → correct service call and arguments).
  A small labelled prompt set runs against a real model only when one is available.

## 10. Build order

1. Skeleton and tooling ✓
2. Domain engine and tests ✓
3. DB, services, REST API and integration tests, seed demo data ✓
4. Vue dashboard: onboarding forms, projection chart, scenario comparison ✓
5. **LangGraph chat: mock provider first, then Ollama** ← next
6. Polish: README, architecture diagram, screenshots, CI

## 11. Decision log

| Decision | Reason |
|---|---|
| Leftover surplus accumulates as cash; goal counts cash + investments | Makes income and expense scenarios affect the goal; matches how savings actually build up |
| Growth assumptions live in the assumption set, not the profile | Profile = facts, assumptions = forecasts, scenarios = overrides |
| No debt interest or inflation in calculations | Keep the Phase 1 foundation simple; both are clean extensions later |
| Debt payment stops when the balance reaches zero | Avoids the absurd case of paying a debt that no longer exists |
| Structured intent router instead of a free tool-calling agent | Reliable with small local models; deterministic and testable |
| Services query the session directly; no repository classes | Queries are one-liners; an extra layer would add indirection without benefit at this size |
| Services take and return domain objects; money becomes `Decimal` only in the database | API and chat never handle records; the Decimal/float conversion lives in one module (`services/mapping.py`) |
| Creating a goal makes it active and deactivates the previous one | One active goal without forcing the user to delete history; enforced by a partial unique index |
| Comparison = built-in scenarios, then saved ones; built-in names are reserved | Saved scenarios extend the defaults instead of duplicating them |
| Assumption presets are added automatically at startup; demo data only on request (`python -m app.seed`) | The app needs assumptions to project anything, but a real user enters their own finances. Presets are never overwritten once stored |
| Migrations run at server startup | A single-user local app shouldn't need a manual migration step |
| Frontend types generated from the OpenAPI description, checked in; a backend test fails if the copy is stale | The UI can't silently drift from the API contract |
| Vite dev proxy (`/api` -> FastAPI) instead of CORS | Same-origin in development; nothing to configure or secure |
| Projection chart hand-drawn in SVG, no chart library | One line chart with custom annotations (target, target date, goal marker); full control of accessibility (keyboard crosshair, table view) and styling for ~200 lines |
| Dates formatted with a fixed month list, not `Intl` | `Intl` en-IE output differs between browsers ("Sep" / "Sept"); the UI must read "1 Sep 2026" everywhere |
| TypeScript pinned to 5.x | `openapi-typescript` and the Vue tooling don't support TypeScript 7 yet |
| Rates typed as percentages in forms, stored as decimals | People think "5%", the engine uses 0.05; the UI converts units only, never computes |
| A goal's target date is validated when the goal is created (this month up to 50 years ahead) | A saved goal can always be projected; the rule lives once in the domain (`months_to_target_date`) |
| Validation errors shown next to their field, taken from the API's 422 response | One source of truth for the rules (Pydantic + domain); the browser's own checks only add early feedback |
| Differences between scenarios (months earlier, euros more) computed in the domain (`delta_from_baseline`) and returned by the API | Subtracting two results is financial maths; the UI only formats |
| Income and expenses accept deltas as well as absolute values | "Spend €200 less" must not require the chat to compute 1,700 − 200; the engine applies the change |
| Chat state is plain JSON; every projection intent runs as a comparison with the current plan | The checkpointer stores no custom classes; what-if answers get their difference from the domain, never from the LLM |
| Clarifications and refusals are always templated, even with an LLM | They carry no figures and must follow the language rules exactly |
| Rules parse first; the LLM only when the rules can't place a message | Measured: letting phi3 override the rules lowered accuracy (74% vs 86%), because its plausible-but-wrong answers pass number checks |
| LLM output is checked deterministically; failures fall back silently | Numbers in a parsed request must appear in the message; reworded replies must copy every figure as a whole phrase from the facts |
| Replies are templated by default; LLM rewording is opt-in (`OLLAMA_REWRITE_REPLIES`) | A small model's rewording introduced factual errors; exact, checkable wording matters more than style in a finance tool |
| The model warms up in a background thread at startup | Ollama's first load took ~90 s; the API is usable immediately and the chat falls back to rules until the model answers |
| Comparison chart: one line per scenario in fixed categorical colours, legend + tooltip + table instead of end labels | End labels of converging lines collide; colour follows the scenario, never its position; at most 8 hues, extra scenarios appear in the table only |
| Ollama as default provider | Free, local, private; provider stays configurable |
| English UI, `en-IE` formatting, dates as "1 Jun 2032" | EUR with English conventions; unambiguous dates |
