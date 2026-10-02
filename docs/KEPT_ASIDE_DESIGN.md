# Money kept aside: a goal that doesn't use everything you have

Until now every goal counted **all** of today's cash and investments. With €10,000 saved and
€10,000 invested, a €20,000 car showed as "already covered". People rarely plan that way:
they keep an emergency fund, and don't want to sell long-term investments for a car.

So a goal can now **keep money aside**: an amount of savings and an amount of investments that
the goal doesn't use. The rules from the earlier phases still hold: all maths in the domain,
the model never calculates, the assumptions are always shown, and no advice.

## 1. What the person sets

Two amounts on the goal, both €0 by default (so nothing changes for existing goals):

- **Keep in savings:** e.g. €5,000 of cash this goal doesn't use (an emergency fund).
- **Keep in investments:** e.g. €7,000 of today's investments this goal doesn't use.

Decided with the user (2 Oct 2026): amounts rather than percentages; one per pot; money
saved or invested from now on counts fully; set on the goal and usable as a what-if.

## 2. The model

What counts towards the goal at the end of each month:

```
counted = max(0, cash − keep_savings) + max(0, investments − keep_investments × G)
```

- **Kept savings are a fixed amount:** cash earns nothing in the model, so €5,000 kept stays
  €5,000.
- **Kept investments keep growing, and their growth isn't counted either.** `G` is the growth of
  the investments since today (in the simulated futures, each future's own growth). The €7,000
  set aside is a slice of the portfolio with its own returns; the goal can't count the gains
  of money it promised not to use.
- **A pot that falls below its kept amount counts as nothing,** never as a negative (if
  spending draws the cash down, the goal simply has none of that pot until it recovers).
- **Future savings count fully,** as today: the leftover surplus adds to cash above the kept
  amount, and new contributions add to investments above it.

Everything that compared cash + investments with the target now compares the **counted**
amount: goal progress today, the goal date, the value on the target date, the shortfall,
"needed per month" (counting `max(0, cash − keep_savings) + (investments − keep_investments)
× G`), the simulated futures (per future), and "what it would take".

## 3. What the person sees

- **Your plan, goal form:** "Money this goal doesn't use (optional)", with "Keep in savings"
  and "Keep in investments". Empty means €0.
- **Projection:** when something is kept aside, the chart is titled **"Counted towards the goal
  over time"** and plots the counted amount, so the line meets the target exactly when the goal
  is reached; its tooltip and the table view add "Kept aside" (and the table "Counted").
- **Where you are today:** progress counts only the counted money, with "€15,000 kept aside, not
  counted" next to it.
- **Kept aside** (a card on Projection, only when something is kept): what the kept money is
  on the target date, so it doesn't look like it disappears. Savings stay the amount kept (or
  "Cash falls below the €5,000 kept" if spending draws them down); investments show today's
  amount and their growth at the assumed return; the total kept aside; and cash + investments
  altogether. All of it from the API (`ScenarioResult.kept_aside`), never added up in the UI.
- **What-ifs** (Compare form, chat): "what if I keep €5,000 in savings?" (`keep_savings`),
  "what if I don't touch my investments?" (`keep_all_investments`: all of today's investments,
  whatever they are). A what-if amount replaces the goal's own amount for that pot only.
  Asking whether to keep money aside ("should I keep an emergency fund?") is still declined as
  advice.
- **Describe your plan:** "I want to keep 5k as an emergency fund" fills "Keep in savings", and
  isn't read as an emergency-fund goal. "I don't want to touch my investments" fills "Keep in
  investments" with the investments amount once it is known, and follows it if it is corrected;
  an amount said later replaces it. "I keep 10k in my savings account" says what there is (cash),
  not what is kept aside, unless the sentence says "aside", "emergency", "buffer" or similar.
- **Summaries:** a **"Kept aside"** point after the goal: "€5,000 of savings and €10,000 of
  investments not counted for this goal; about €16,025 by the target date."

### Worked example (the engine's numbers)

Take-home €2,500, expenses €1,900, €300 invested a month, €10,000 saved and €10,000 invested; a
€20,000 car by 1 Oct 2028; base assumptions (5% return), medium risk.

| | Nothing kept aside | Keep €5,000 of savings and all investments |
|---|---|---|
| Counted today | €20,000: already covered | €5,000 (€15,000 kept aside) |
| Goal reached | today | 1 Nov 2028, a month late (€108 short on the target date) |
| Needed per month to be on time | – | €596 (€300 today) |
| On time in simulated futures | all | about 45% of 1,000 |
| To be on time in 9 of 10 futures | – | about €656 a month |
| Kept aside on 1 Oct 2028 | – | €16,025 (investments +€1,025) |

Cash + investments on the target date are €35,917 either way: keeping money aside changes what
the goal may count, not what the person has.

## 4. Data and API

Two columns on goals (`keep_savings`, `keep_investments`, money ≥ 0, default 0) with a
migration; the goal schemas, the draft and the what-if overrides gain the same two fields (the
overrides also `keep_all_savings` / `keep_all_investments`, resolved in the domain by
`ScenarioOverrides.kept_aside(goal, profile)`). The
snapshots gain `counted` (what counts towards the goal that month) and `kept_savings` /
`kept_investments` (what is kept aside that month: the kept amount, or what is left of it if
the pot fell below it), computed by the domain, so counted + kept = cash + investments. The
result gains `kept_aside` (today, on the target date, the investments' growth, and cash +
investments altogether) for the card and the summary.

## 5. Testing

- Kept amounts of 0 give exactly today's results (every existing test still passes).
- The car example: €8,000 counted today; the goal date and "needed per month" match a plan
  with only that money.
- Kept investments grow with the same returns as the rest (fixed seed), and their growth is
  never counted; with zero volatility the futures match the projection.
- A pot below its kept amount counts as 0.
- "Needed per month" fed back into the projection reaches the target exactly.
- What-ifs, the draft and the chat with kept amounts; the grounding checks still hold.

## 6. Build order

1. **Domain:** `counted` in the projection, goal date, progress, required contribution, the
   simulated futures and "what it would take"; tests.
2. **Data and API:** migration, goal schemas, overrides; integration tests.
3. **Your plan and Projection:** the goal form fields, "Counted towards the goal" on the chart,
   table and progress.
4. **What-ifs, chat and describe-your-plan:** overrides, rules and wording; summaries.
5. **README** and this doc's decisions.

## 7. Decision log

| Decision | Reason |
|---|---|
| Amounts, one per pot (user's choice) | "Keep €5,000 as an emergency fund" is how people say it; separate pots say which money stays |
| Kept investments keep their own growth | A slice set aside today grows with the portfolio; counting its gains would quietly use money the goal promised not to touch |
| Future savings count fully | The kept amounts are about today's money; anything else needs a second set of rules for every month |
| A pot below its kept amount counts 0, never negative | The goal can't owe money to the emergency fund; it just has none of that pot |
| The chart shows the counted amount when something is kept | So the line meets the target exactly when the goal is reached, as before |
| Show the kept-aside money and its growth (user's suggestion) | Keeping money aside shouldn't look like losing it; counted + kept always adds up to cash + investments |
| "Don't touch my investments" is its own what-if flag, not an amount | The chat must not copy the investments figure into the question; the domain resolves "all of it" from the plan, so the model still never handles a number it wasn't given |
| In a description, "all of my investments" follows that amount until another is said | A correction ("sorry, 9k invested") shouldn't leave a stale kept amount behind; copying is all the code does, no arithmetic |
| "I keep 10k in my savings account" is cash, not money kept aside | In everyday speech "keep" often just means "have"; reading it as kept aside would quietly remove the money from the goal |
| A keep sentence is never read as the goal | "Emergency fund" is also a goal type, so "keep 5k as an emergency fund" would otherwise turn a car goal into an emergency-fund goal |
| The summary says what is kept aside as its own point | It's a fact the projection depends on, like the assumptions; leaving it out would make "€5,000 counted" look like an error |
