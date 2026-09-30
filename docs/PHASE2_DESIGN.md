# Phase 2: How sure is this projection?

Phase 1 answers "when do I reach my goal?" with one line, under assumptions the user can see.
Phase 2 shows how much that answer depends on the one assumption that varies most in real
life, investment returns, by simulating many possible futures (Monte Carlo).

The Phase 1 rules still hold: all maths lives in the domain layer (standard library only), the
language model never calculates, assumptions are always shown, and the wording never gives
advice.

## 1. Scope

**In Phase 2:** random yearly investment returns; an "investment risk" setting (low, medium,
high); the probability of reaching the target by the target date, with its precision; how that
probability grows year by year; how large the shortfall typically is in the futures that miss; a
band of likely outcomes on the projection chart; the range of likely goal dates; a deterministic
**market-drop what-if** ("what if investments fall 30% next year?"). Then the probability per
scenario on the Compare page, and chat questions ("How likely am I to reach my goal?", "What if
the market falls 30%?"). Last, if everything else is solid: **"what would it take"**, the monthly
investment that reaches the target on time in a chosen share of futures (e.g. 8 in 10).
Optional polish: a few example futures drawn on the chart.

**Not in Phase 2:** random salary, expenses or inflation; market data or historical returns;
correlations or random crash regimes (the market drop is one user-chosen, deterministic shock);
optimising anything other than the monthly investment; recommendations. Each can be added later on top of the same simulator.

## 2. Model

### 2.1 What is random

Only the **investment return**, drawn once per year for each simulated future. Everything else
(income, expenses, contributions, debt, cash) follows exactly the Phase 1 monthly algorithm, so
the simulator is the existing engine run many times with different yearly returns.

### 2.2 Distribution of a year's return

The gross return of year *y* in one simulated future is lognormal:

```
G_y = exp(X_y),   X_y ~ Normal(μ, σ²)
μ   = ln(1 + r)          r = the assumption set's annual return (e.g. 0.05)
σ   = the volatility     from the investment risk level (e.g. 0.10)
```

- **Lognormal** keeps every year's return above −100%: an investment can't lose more than
  everything.
- **σ is the volatility of yearly log returns**, the standard definition of "annualised
  volatility". The standard deviation of the yearly return itself is slightly larger: for the
  presets here, by 0.1 to 1.3 percentage points (1.3 at high risk with a 7% return).
- **The median future compounds at exactly r.** With μ = ln(1 + r), the median of
  G₁ × … × Gₙ is (1 + r)ⁿ, exactly Phase 1's compounding. So the existing projection line is
  the middle of the simulated futures, not a rival forecast. The *average* yearly return is a
  little higher (about r + σ²/2); the doc and UI describe r as the "typical" return.

Within year *y*, the monthly rate is `(G_y)^(1/12) − 1`, the Phase 1 convention (12 months
compound to exactly that year's return).

### 2.3 Investment risk

A property of the user's portfolio, stored on the profile and editable in "Your plan":

| Level | Volatility σ | Roughly |
|---|---|---|
| Low | 5% | mostly bonds and cash-like funds |
| Medium (default) | 10% | a balanced mix |
| High | 15% | mostly shares |

The levels are illustrative, like the assumption presets, and the volatility is always shown next
to the results. Cash has no risk in the model (it earns nothing, as in Phase 1).

**Risk and return are set separately.** The risk level only widens or narrows the range; the
typical return comes from the assumption set. In reality, riskier investments are usually chosen
*because* they are expected to return more, so comparing risk levels on the same return would
always make low risk look better. The UI therefore never compares risk levels side by side, and
says next to the results: "The risk level sets how widely returns vary; the typical return comes
from your assumptions."

### 2.4 Market-drop what-if (deterministic)

A scenario override `first_year_return`: the return of the first projected year, replacing the
assumed return for months 1–12; later years use the assumed return again. "What if investments
fall 30% next year?" is `first_year_return = −0.30`. It works everywhere a what-if works
(Projection, Compare, chat) and needs no randomness. In the Monte Carlo simulation it fixes the
first year in every future, and later years stay random.

### 2.5 Simulation

- **1,000 simulated futures** per request.
- **Reproducible:** Python's `random.Random(seed)` with a fixed default seed, sent with the
  request and returned with the result. The same plan always gives the same numbers, which
  keeps the engine deterministic and the chat's grounding checks valid.
- **Common random numbers:** when scenarios are compared, every scenario uses the same seed,
  so the same 1,000 return sequences. Differences then come from the scenario, not from luck.
- **Horizon:** each future runs to the target date plus 10 years (at most 50 years), long enough
  to date late goals without simulating decades nobody looks at. Futures that still haven't
  reached the target are reported as "not within the horizon".
- **No NumPy:** the domain stays standard-library only. The expected cost (1,000 futures ×
  up to ~200 months for typical goals) is well under a second; 50-year goals take longer and
  have a performance test.

### 2.6 Outputs

| Output | Definition |
|---|---|
| Probability by the target date | Share of futures whose cash + investments reach the target by the target date |
| Goal-date range | 10th, 50th and 90th percentile of the date each future first reaches the target; the share never reaching it within the horizon |
| Band | 10th, 50th and 90th percentile of cash + investments at each month (the chart's band and middle line) |
| Value on the target date | 10th, 50th and 90th percentile |
| Precision | Half-width of the 95% interval of the probability, 1.96 × √(p(1 − p) / n), in whole percentage points (at most about ±3 for 1,000 futures) |
| Reached by each year | Share of futures that have reached the target by each 1 January, and by the target date |
| Shortfall when missed | In the futures that miss the target date: the median and 90th-percentile shortfall; none when every future reaches it |
| Inputs echoed | Number of futures, seed, risk level, volatility, assumption set |

Percentiles use one fixed method (nearest rank on the sorted values), tested directly.

## 3. Presentation and wording

- Headline: *"In about 72% of 1,000 simulated futures, the goal is reached by 1 Jun 2032."*
  Percentages are rounded to whole numbers; above 99% reads "more than 99%", below 1% "fewer
  than 1%". Never "your chance" or "you will".
- Always shown with it: risk level and volatility, the assumption set, the number of futures, and
  one sentence on what varies ("Investment returns vary from year to year around the assumed
  5%; income, expenses and contributions follow your plan.").
- Chart: the middle 80% of futures (10th to 90th percentile) as a shaded band in the series
  hue, the Phase 1 line on top. Band and line are described in the legend and the table view
  (percentiles at yearly points), so nothing depends on colour alone.
- Goal-date range: *"In the middle 80% of futures, the goal is reached between Mar 2031 and
  Feb 2033."*
- Precision next to the probability: *"about 72% (±3 points: 1,000 futures)"*.
- Reached by year: a small rising curve or list (*"by 2031: 40% · by 2032: 72% · by 2033: 88%"*).
- Shortfall when missed: *"In the futures that miss the target date, they are typically €4,000
  short (€11,000 in the worst tenth)."*
- A short explanation for newcomers: "72% means that in 720 of 1,000 simulated futures the goal
  is reached by the target date."
- "What would it take" (last step): *"To reach the goal by the target date in 8 of 10 simulated
  futures, about €720 a month would need to be invested."* Worded as a figure, never as advice.
- This is still a projection, not a guarantee, and the probability is only as good as the
  assumed return and volatility.

## 4. API

`POST /simulate/uncertainty` with `{assumption_set, overrides, paths, seed}` (all optional, as
in `/simulate`) returns the outputs above. `/simulate` is unchanged. The profile gains
`investment_risk` (`low` / `medium` / `high`, default `medium`), with a database migration.

## 5. Testing

- **No volatility, no randomness:** with σ = 0 every future equals the Phase 1 projection, and
  the probability is 0% or 100%, matching `reaches_goal`.
- **The median is the Phase 1 line:** with contributions set to 0, the 50th-percentile
  investment value equals the deterministic one (the exact lognormal property); with a full
  plan, it stays within a tested tolerance.
- **Ordered percentiles:** 10th ≤ 50th ≤ 90th at every month (property-based, Hypothesis).
- **Reproducible:** the same seed gives identical results; different seeds agree within a few
  percentage points at 1,000 futures.
- **Sensible direction, same random draws:** a higher return or more money coming in never
  lowers any future. Investing more of the surplus instead of keeping it as cash raises the
  typical future but widens the range: in the worst futures the cash would have been worth more
  (cash is safe in the model, investments can fall), so this is tested as such, not as "always
  better".
- **The sampler:** with a fixed seed, the mean and spread of the sampled log returns match μ
  and σ within statistical tolerance.
- **Performance:** a 50-year goal with 1,000 futures stays under a set time budget.
- **Boundaries:** the architecture test still keeps the domain on the standard library
  (`random`, `math`, `statistics`).

## 6. Build order

1. **Domain:** the engine accepts a sequence of yearly returns; the market-drop override; the
   lognormal sampler; the Monte Carlo summary (probability and precision, reached-by-year,
   shortfall when missed, bands, goal dates); tests.
2. **Data and API:** `investment_risk` on the profile (migration, forms), `POST
   /simulate/uncertainty`, integration tests.
3. **Projection page:** the probability headline, the band on the chart, the goal-date range, the
   table view.
4. **Compare:** probability per scenario, on common random numbers.
5. **Chat:** "How likely am I to reach my goal?" and "What if the market falls 30%?", answered
   from the same results, with grounding.
6. **What would it take:** the monthly investment for a chosen share of futures (a search over
   simulations on common random numbers).
7. *Optional:* example futures on the chart.

## 7. Decision log

| Decision | Reason |
|---|---|
| Only investment returns are random | They vary most and matter most; one source of randomness is explainable and testable |
| Yearly draws, not monthly | Matches the engine's yearly steps and how returns are quoted; far fewer draws |
| Lognormal, with μ = ln(1 + r) | Returns can't fall below −100%; the median future compounds at exactly r, so the Phase 1 line is the middle of the band |
| Risk as a profile setting (low / medium / high), not per assumption set | Volatility describes the portfolio; the assumption sets describe expectations about the future. Two separate ideas are easier to explain |
| Fixed, returned seed | Reproducible numbers keep the engine deterministic and the chat's answers verifiable |
| Common random numbers across scenarios | Comparisons show the effect of the change, not of different luck |
| Standard library only, no NumPy | Keeps the domain rule; 1,000 futures are fast enough in pure Python |
| Whole-number percentages, "simulated futures" wording | Avoids false precision and promises |
| Show the probability's precision (±) | 1,000 futures estimate the probability to about ±3 points; saying so is honest and teaches what a simulation can tell |
| Report how large the misses are, not only how often | 70% with small misses and 70% with large ones call for different reactions |
| Market drop as a deterministic override (`first_year_return`) | Relatable and explainable, works in every view and in the chat, and needs no randomness |
| Risk and return stay separate; risk levels are never compared side by side | Pairing them would hide an assumption; comparing them on one return would make low risk always look better |
| "What would it take" last | The most practical output, but it needs many simulations per answer and careful wording |
