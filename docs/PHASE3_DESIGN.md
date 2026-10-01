# Phase 3: The AI as a guide

Phases 1 and 2 built a deterministic engine with many answers on screen. Phase 3 uses the
language model to make them easier to reach and to understand: a new user can **describe their
situation in their own words** instead of filling in a form, and each page can **explain itself
in plain language**.

The rules from Phases 1 and 2 still hold: all maths lives in the domain layer, the model never
calculates or invents a number, every model output is checked by code before anyone sees it,
everything works without a model (mock provider), and the wording never gives advice.

## 1. Scope

**In Phase 3:**

- **Describe your plan:** a text box on "Your plan" turns a description ("I take home about
  2,400 a month, spend 1,600, have 8k saved and 5k in an ETF; I want 60k for a house deposit by
  2032") into a draft of the existing forms. Missing details are asked for, one short question
  at a time. Nothing is saved until the user checks the forms and clicks Save.
- **"What does this mean for me?":** a button on the Projection and Compare pages writes a short
  summary of the page in plain language, from the engine's results, with every figure checked.
- **A simpler first visit:** one sentence at the top of each page saying what it answers, and the
  "How sure is this?" details folded away until asked for.
- **Evaluation** of both AI features, like the chat's.

**Not in Phase 3:** importing bank exports (a candidate for Phase 4), storing the descriptions
or summaries, voice input, hosted models, recommendations of any kind.

## 2. Describe your plan

### 2.1 What the user sees

On "Your plan", above the forms: *"Describe your situation in your own words, or fill in the
form below."* After each message:

- the forms below are filled with the draft, each filled field marked "from your description";
- a short list of what was understood ("Take-home pay: €2,400 a month"), so a misreading is
  visible at once;
- one question for the most important missing piece ("How much do you invest each month? If
  nothing yet, say 0."), with a short line under it listing everything still missing ("Still
  missing: goal date · optional: investments, debt"). The answer goes in the same box; a short
  answer ("300", "no") goes to the question asked, and a longer one can fill several fields at
  once. Questions can be skipped, and the forms can always be typed in directly.

The user then checks the forms and saves them as today. The description is never stored.

### 2.2 What the draft contains

The profile fields (take-home pay, other income, expenses, cash, investments, monthly
investment, debt and its payment, age) and the goal (name, type, amount, target date). Required
before saving, as today: take-home pay, expenses, and the goal's name, amount and date.

### 2.3 Extraction without calculation

The extractor only copies what the user wrote, with its context:

- **Every number must appear in the message** (with "8k", "€8,000" and "8.000" read as the same
  value), as in the chat. A value that fails the check is dropped, never guessed.
- **Code does the arithmetic, and shows it.** "Rent 900 and about 700 for everything else" is
  extracted as two parts; the domain adds them and the draft shows "€1,600 (€900 + €700)". "36k a
  year" is extracted with its period; the domain converts it and the draft shows "€3,000 a month
  (€36,000 a year ÷ 12)", with a reminder that the simulator uses take-home pay.
- **Percentages of something are asked about, not computed by the model.** "20% deposit on a
  300k house" gives a question: "So the goal is €60,000 (20% of €300,000)?", where the €60,000
  comes from the domain, and the user confirms.
- **Dates:** "by 2032" becomes 1 Jan 2032 unless a month is named ("June 2032" -> 1 Jun 2032),
  and the draft says which.

### 2.4 Who extracts

The same strategy the chat measured: **rules first, the model for the rest.** A rule-based
extractor (the mock provider) recognises common phrasings; the model is asked only for the fields
the rules couldn't fill, through a flat JSON form like the chat's `ModelRequest`. Where both give
a value, the rules win. Without a model, the rules alone fill what they can and the questions do
the rest.

### 2.5 API

`POST /plan/draft` with `{message, draft}` returns `{draft, understood, questions, parsed_by}`.
It is stateless: the browser sends the current draft back with each message, so nothing about
the conversation is kept on the server.

## 3. "What does this mean for me?"

### 3.1 What the user sees

A button at the top of the Projection page (and of Compare). It shows three to five sentences,
for example:

> Under the base assumptions, you reach €80,000 on 1 Aug 2031, 10 months before the target
> date. In about 93% of 1,000 simulated futures you are on time; to be on time in 9 of 10,
> about €840 a month would need to be invested instead of €400 today.

Below it: "Written by qwen2.5:3b and checked against the figures above", or "Summary from
templates" when no model is used or the model's text failed a check.

### 3.2 How it is built

1. **Facts, by code.** The backend runs the same projection and simulation as the page and turns
   them into a short list of factual sentences, chosen by rules: the goal status, the share of
   futures on time, what it would take, and notes only when they apply (behind target, a warning
   such as running out of cash, the cash effect).
2. **Wording, by the model.** The model rewrites the facts as a short summary.
3. **Checks, by code.** The summary is rejected unless every figure is copied exactly from the
   facts (the Phase 1 `check_explanation`: whole amounts, dates, durations and percentages; no
   durations in words; no advice words such as "should" or "recommend").
4. **Fallback.** The facts themselves, joined, are the template summary.

The backend computes the facts itself from the stored plan, so the summary never depends on
figures sent by the browser.

### 3.3 Compare

The same pipeline on the comparison: which scenarios change the goal date or the share on time
most, stated as differences, never as "the best option".

### 3.4 API

`POST /explain/projection` and `POST /explain/compare`, each with `{assumption_set}`, return
`{summary, facts, worded_by}`.

## 4. A simpler first visit

- Each page starts with one sentence: what it answers ("When do you reach your goal, and how
  sure is that?").
- The "How sure is this?" card keeps the headline and "What it would take" visible; the goal-date
  range, value range, shortfall and "reached by" list move into "Show details".
- New users still start on "Your plan", now with the description box first.

## 5. Evaluation and testing

- **Extraction:** a labelled set of about 30 descriptions, some messy (mixed periods, parts to
  add, a percentage of a price, irrelevant details). Scored per field: correct, missing or wrong,
  where wrong is the costly kind. Rules alone, model alone, and rules then model, as for the chat
  (`python -m app.agents.evaluate_setup`).
- **Summaries:** run on a set of plans (on track, behind, already reached, high risk, debt, short
  horizon). Measured: how often the model's summary passes the checks, and why it fails when it
  doesn't. A short manual review (faithful, readable, no advice) is recorded in the README.
- **Tests:** the extractor never outputs a number that isn't in the message; parts and periods
  are combined by the domain; checks reject invented or computed figures (e.g. €60,000 written by
  the model from "20% of 300k"); the API never saves a draft; pages work with the mock provider.

## 6. Build order

1. **Draft contract and rules:** the draft schema, the rule-based extractor, the number checks,
   and the domain's sums and period conversions; tests.
2. **Model extraction:** the model's form and its checks; the labelled set and the evaluation.
3. **Describe your plan:** `POST /plan/draft` and the box on "Your plan" filling the forms.
4. **Projection summary:** facts, template, model wording and checks; `POST /explain/projection`;
   the button.
5. **Compare summary.**
6. **First visit:** page sentences, "Show details", README.

## 7. Decision log

| Decision | Reason |
|---|---|
| The model guides, the engine still answers | Keeps the guarantee that no figure comes from the model, while giving the model real work |
| A draft the user confirms, never an automatic save | Extraction can be wrong; a person checks before anything changes |
| One question at a time, plus a "still missing" line | Easy for a first-time user, while someone who knows their numbers can answer several at once |
| Rules first, model for the rest | Measured on the chat: a small model going first made results worse |
| Arithmetic on extracted values in the domain, shown in the draft | "€900 + €700" and "÷ 12" are calculations, so code does them, visibly |
| Percent-of-price goals confirmed by a question | The user decides what the goal is; the simulator only does the sum |
| Stateless draft API | Nothing about the description is kept on the server |
| Summaries from facts chosen by code | The model can only reword what code decided is true and relevant |
| Template fallback for every AI feature | Everything works without a model, and a failed check is never shown |
