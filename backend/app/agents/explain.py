"""Deterministic replies built from structured results: the mock provider's explanations,
the language model's fallback, and every clarification or refusal.

Figures are formatted from the API's already-rounded values; nothing is computed here.
Wording follows the project rules: "under these assumptions", "a projection, not a
guarantee", never advice.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.agents.intents import (
    CompareScenarios,
    ExplainAssumptions,
    GoalDate,
    Intent,
    Likelihood,
    RequiredContribution,
    RunProjection,
    WhatIf,
)
from app.schemas.plan import Rates
from app.schemas.scenarios import ComparedScenarioOut, OverridesIn, ScenarioResultOut
from app.schemas.uncertainty import ComparedFuturesOut, FuturesComparisonOut

DISCLAIMER = "This is a projection, not a guarantee."

SIMPLIFICATIONS = (
    "no taxes on investment gains",
    "no investment fees (the return is after fees)",
    "no interest on debt",
    "amounts are not adjusted for inflation",
    "salary growth applies to net income",
    "rates stay constant every year",
    "cash earns no interest",
)

EXAMPLES = (
    "“Am I on track?”, “When will I reach my goal?”, “How much do I need to invest each "
    "month?”, “What if I invest €200 more per month?”, “How likely am I to reach my goal?”, "
    "“What if the market falls 30% next year?”, “Compare my options”"
)

RISK_LABELS = {"low": "low", "medium": "medium", "high": "high"}

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


@dataclass(frozen=True)
class Facts:
    """Everything an explanation may use: the request and the engine's rounded results."""

    intent: Intent
    results: list[ComparedScenarioOut]
    assumption_set: str | None
    rates: Rates | None
    question: str = ""
    futures: FuturesComparisonOut | None = None
    """Simulated futures of the same scenarios, for likelihood questions."""


# ---- formatting (same conventions as the UI: €91,962, 1 Jun 2032, 5%) ------------------------


def eur(value: float) -> str:
    whole = Decimal(str(abs(value))).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    return f"{'−' if value < 0 and whole else ''}€{whole:,}"


def signed_eur(value: float) -> str:
    text = eur(value)
    return text if text == "€0" or text.startswith("−") else f"+{text}"


def day(value: date | str) -> str:
    """date(2032, 6, 1) or "2032-06-01" -> "1 Jun 2032"."""
    d = value if isinstance(value, date) else date.fromisoformat(value)
    return f"{d.day} {_MONTHS[d.month - 1]} {d.year}"


def percent(rate: float) -> str:
    return f"{Decimal(str(rate)) * 100:.2f}".rstrip("0").rstrip(".") + "%"


def month_year(value: date | str) -> str:
    """ "2030-11-01" -> "Nov 2030"."""
    d = value if isinstance(value, date) else date.fromisoformat(value)
    return f"{_MONTHS[d.month - 1]} {d.year}"


def share(value: float) -> str:
    """A share of simulated futures in whole percentages, never claiming certainty:
    0.948 -> "about 95%", 1 -> "more than 99%", 0 -> "fewer than 1%"."""
    if value > 0.99:
        return "more than 99%"
    if value < 0.01:
        return "fewer than 1%"
    whole = Decimal(str(value * 100)).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    return f"about {whole}%"


def points(margin: float) -> str:
    """Precision of a share: 0.0138 -> "±1 point"."""
    whole = int(Decimal(str(margin * 100)).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return "less than ±1 point" if whole < 1 else f"±{whole} point{'s' if whole != 1 else ''}"


def points_difference(points: int) -> str:
    """The API's difference between two shares as displayed, in whole points: 5 -> "5 points
    more", -1 -> "1 point fewer", 0 -> "the same share"."""
    if points == 0:
        return "the same share"
    size = abs(points)
    return f"{size} point{'s' if size != 1 else ''} {'more' if points > 0 else 'fewer'}"


def duration(months: int) -> str:
    years, rest = divmod(months, 12)
    parts = []
    if years:
        parts.append(f"{years} year{'s' if years != 1 else ''}")
    if rest or not years:
        parts.append(f"{rest} month{'s' if rest != 1 else ''}")
    return " ".join(parts)


def relative_timing(months: int) -> str:
    """For lists: 4 -> "4 months earlier", -1 -> "1 month later", 0 -> "same time"."""
    if months == 0:
        return "same time"
    return f"{duration(abs(months))} {'earlier' if months > 0 else 'later'}"


def months_earlier(months: int) -> str:
    if months == 0:
        return "at the same time as"
    return f"{duration(abs(months))} {'earlier' if months > 0 else 'later'} than"


# ---- replies ------------------------------------------------------------------------------------


def template_reply(facts: Facts) -> str:
    if isinstance(facts.intent, ExplainAssumptions):
        return _assumptions_reply(facts)
    return f"{template_body(facts)}\n\n{footer(facts)}"


def footer(facts: Facts) -> str:
    """The assumptions and the disclaimer: always appended by code, never by a model."""
    return f"{assumptions_line(facts)} {DISCLAIMER}"


def template_body(facts: Facts) -> str:
    """The facts of a projection answer, in plain sentences (without the footer)."""
    intent = facts.intent
    current = facts.results[0].result
    if isinstance(intent, Likelihood):
        assert facts.futures is not None
        body = _likelihood(facts.futures, facts.results, intent.overrides)
    elif isinstance(intent, WhatIf):
        body = _what_if(facts.results, intent.overrides)
    elif isinstance(intent, CompareScenarios):
        body = _comparison(facts.results)
    elif isinstance(intent, RequiredContribution) and intent.share is not None:
        assert facts.futures is not None
        body = _required_in_futures(current, facts.futures)
    elif isinstance(intent, RequiredContribution):
        body = _required(current)
    elif isinstance(intent, GoalDate | RunProjection):
        body = goal_sentence(current)
        if isinstance(intent, RunProjection) and current.months_to_goal != 0:
            body += (
                f" On the target date the projection shows "
                f"{eur(current.projected_value_at_target_date)} in cash and investments."
            )
    else:  # pragma: no cover - the graph only explains answerable intents
        raise ValueError(f"no template for {intent.kind}")
    return body


def assumptions_line(facts: Facts) -> str:
    r = facts.rates
    assert r is not None
    return (
        f"Assumptions: {facts.assumption_set} set, {percent(r.annual_return)} return, "
        f"{percent(r.annual_salary_growth)} salary growth and "
        f"{percent(r.annual_expense_growth)} expense growth a year."
    )


def goal_sentence(r: ScenarioResultOut) -> str:
    target, target_day = eur(r.target_amount), day(r.target_date)
    if r.months_to_goal == 0:
        return f"Your cash and investments already cover the {target} goal."
    if r.reaches_goal and r.projected_goal_date and r.months_to_goal is not None:
        early = r.months_to_target_date - r.months_to_goal
        timing = "on the target date" if early == 0 else f"{duration(early)} before the target date"
        return (
            f"Under these assumptions, you reach the {target} goal on "
            f"{day(r.projected_goal_date)}, {timing} ({target_day})."
        )
    later = (
        f"It is reached on {day(r.projected_goal_date)} instead."
        if r.projected_goal_date
        else "It isn't reached within 50 years."
    )
    return (
        f"Under these assumptions, the {target} goal is not reached by {target_day}: "
        f"{eur(r.shortfall)} short. {later}"
    )


def _required(r: ScenarioResultOut) -> str:
    target, target_day = eur(r.target_amount), day(r.target_date)
    if r.required_monthly_contribution is None:
        return (
            f"The target date ({target_day}) has arrived and the {target} goal isn't reached, "
            "so no monthly amount can close the gap in time."
        )
    if r.required_monthly_contribution == 0:
        return (
            f"Your current cash and investments already grow to {target} by {target_day} "
            "under these assumptions, without further monthly investment."
        )
    return (
        f"To reach {target} by {target_day}, about {eur(r.required_monthly_contribution)} a "
        f"month would need to be invested from next month, at the assumed "
        f"{percent(r.assumptions.annual_return)} return. Today {eur(r.monthly_contribution)} "
        f"is invested each month, and the monthly surplus is {eur(r.monthly_surplus)}."
    )


def _required_in_futures(r: ScenarioResultOut, futures: FuturesComparisonOut) -> str:
    """What it would take in a chosen share of simulated futures, next to the amount at the
    assumed return and today's figures."""
    target, target_day = eur(r.target_amount), day(r.target_date)
    (level,) = futures.scenarios[0].required_monthly_investment
    how_sure = f"at least {percent(level.share)} of {futures.paths:,} simulated futures"
    if level.monthly_amount is None:
        return (
            f"The target date ({target_day}) has arrived and the {target} goal isn't reached in "
            f"{how_sure}, so no monthly amount can close the gap in time."
        )
    if level.monthly_amount == 0:
        text = (
            f"Your current cash and investments already grow to {target} by {target_day} in "
            f"{how_sure}, without further monthly investment."
        )
    else:
        text = f"To reach {target} by {target_day} in {how_sure}, about " + (
            f"{eur(level.monthly_amount)} a month would need to be invested from next month."
        )
    if r.required_monthly_contribution is not None:
        text += (
            f" At the assumed {percent(r.assumptions.annual_return)} return in every year it is "
            f"{eur(r.required_monthly_contribution)}."
        )
    return text + (
        f" Today {eur(r.monthly_contribution)} is invested each month, and the monthly surplus is "
        f"{eur(r.monthly_surplus)}. Like the assumed-return figure, this counts today's cash and "
        "investments plus the monthly amount, not the leftover surplus. Investment returns vary "
        f"around the assumed return ({RISK_LABELS[futures.investment_risk]} investment risk: "
        f"about {percent(futures.volatility)} a year)."
    )


def describe_overrides(o: OverridesIn) -> str:
    parts = []
    if o.monthly_investment_contribution == 0:
        parts.append("no monthly investment")
    elif o.monthly_investment_contribution is not None:
        parts.append(f"{eur(o.monthly_investment_contribution)} invested each month")
    if o.monthly_investment_contribution_delta:
        more = "more" if o.monthly_investment_contribution_delta > 0 else "less"
        parts.append(
            f"{eur(abs(o.monthly_investment_contribution_delta))} {more} invested each month"
        )
    if o.monthly_net_income is not None:
        parts.append(f"a take-home pay of {eur(o.monthly_net_income)} a month")
    if o.monthly_net_income_delta:
        more = "more" if o.monthly_net_income_delta > 0 else "less"
        parts.append(f"{eur(abs(o.monthly_net_income_delta))} {more} take-home pay a month")
    if o.monthly_expenses is not None:
        parts.append(f"expenses of {eur(o.monthly_expenses)} a month")
    if o.monthly_expenses_delta:
        more = "more" if o.monthly_expenses_delta > 0 else "less"
        parts.append(f"{eur(abs(o.monthly_expenses_delta))} {more} spent each month")
    if o.annual_return is not None:
        parts.append(f"a {percent(o.annual_return)} investment return")
    if o.annual_salary_growth is not None:
        parts.append(f"salary growth of {percent(o.annual_salary_growth)} a year")
    if o.annual_expense_growth is not None:
        parts.append(f"expense growth of {percent(o.annual_expense_growth)} a year")
    if o.keep_all_savings:
        parts.append("all of today's savings kept aside")
    elif o.keep_savings is not None:
        parts.append(f"{eur(o.keep_savings)} of savings kept aside")
    if o.keep_all_investments:
        parts.append("all of today's investments kept aside")
    elif o.keep_investments is not None:
        parts.append(f"{eur(o.keep_investments)} of investments kept aside")
    if o.first_year_return is not None:
        move = "fall" if o.first_year_return < 0 else "rise"
        parts.append(
            f"a {percent(abs(o.first_year_return))} {move} in investments in the first year"
        )
    return " and ".join(parts) if parts else "no changes"


def _what_if(results: list[ComparedScenarioOut], overrides: OverridesIn) -> str:
    current, what_if = results[0].result, results[1]
    r, delta = what_if.result, what_if.vs_baseline
    changes = describe_overrides(overrides)
    if r.projected_goal_date is None:
        reached = "the goal isn't reached within 50 years"
    elif delta.goal_months_earlier is None or current.projected_goal_date is None:
        reached = f"the goal is reached on {day(r.projected_goal_date)}"
    else:
        reached = (
            f"the goal is reached on {day(r.projected_goal_date)}, "
            f"{months_earlier(delta.goal_months_earlier)} the current plan "
            f"({day(current.projected_goal_date)})"
        )
    text = (
        f"With {changes}, {reached}. On the target date ({day(r.target_date)}) the "
        f"projection shows {eur(r.projected_value_at_target_date)}, "
        f"{signed_eur(delta.value_at_target_difference)} compared with the current plan."
    )
    cautions = [w.message for w in r.warnings if w.code != "debt_paid_off"]
    if cautions:
        text += f" Note: {cautions[0]}"
    if overrides.first_year_return is not None:
        text += (
            " This uses one fixed return for the first year; ask “How likely is that?” to see "
            "it over simulated futures, where later years vary too."
        )
    return text


def _likelihood(
    futures: FuturesComparisonOut, results: list[ComparedScenarioOut], overrides: OverridesIn | None
) -> str:
    target = results[0].result
    goal, target_day = eur(target.target_amount), day(target.target_date)
    count = f"{futures.paths:,}"
    current = futures.scenarios[0]
    if overrides is None:
        shown = current
        text = (
            f"In {share(shown.probability_by_target_date)} of {count} simulated futures, the "
            f"{goal} goal is reached by {target_day} (precision "
            f"{points(shown.probability_margin)})."
        )
    else:
        shown = futures.scenarios[1]
        text = (
            f"With {describe_overrides(overrides)}, the {goal} goal is reached by {target_day} "
            f"in {share(shown.probability_by_target_date)} of {count} simulated futures: "
            f"{points_difference(shown.points_difference)} than with the current plan "
            f"({share(current.probability_by_target_date).removeprefix('about ')})."
        )
        invests_more = (overrides.monthly_investment_contribution_delta or 0) > 0 or (
            overrides.monthly_investment_contribution is not None
            and overrides.monthly_investment_contribution > target.monthly_contribution
        )
        if invests_more and shown.probability_difference < 0:
            text += (
                " Investing more moves money from cash, which is safe in the model, into "
                "investments, which vary: typical futures end higher, but some bad ones lower."
            )
    text += f" {_goal_date_range(shown)}"
    if s := shown.shortfall_when_missed:
        text += (
            f" In the futures that miss the target date, they are typically {eur(s.p50)} short "
            f"({eur(s.p90)} or more in the worst tenth of those)."
        )
    rates = target.assumptions
    return text + (
        f" Investment returns vary from year to year around the assumed "
        f"{percent(rates.annual_return)} ({RISK_LABELS[futures.investment_risk]} investment "
        f"risk: about {percent(futures.volatility)} a year); income, expenses and contributions "
        "follow the plan."
    )


def _goal_date_range(f: ComparedFuturesOut) -> str:
    d = f.goal_dates
    if d.p10 and d.p50 and d.p90:
        return (
            f"In the middle 80% of futures, the goal is reached between {month_year(d.p10)} "
            f"and {month_year(d.p90)}."
        )
    if d.p10:
        return (
            f"In {share(f.not_reached_share).removeprefix('about ')} of futures, it is not "
            "reached within the simulated period."
        )
    return "In most futures, it is not reached within the simulated period."


def _comparison(results: list[ComparedScenarioOut]) -> str:
    baseline = results[0]
    b = baseline.result
    reached = day(b.projected_goal_date) if b.projected_goal_date else "not within 50 years"
    lines = [
        f"{baseline.name}: goal reached {reached}, "
        f"{eur(b.projected_value_at_target_date)} on the target date ({day(b.target_date)})."
    ]
    for s in results[1:]:
        r, delta = s.result, s.vs_baseline
        when = day(r.projected_goal_date) if r.projected_goal_date else "not within 50 years"
        timing = (
            f" ({relative_timing(delta.goal_months_earlier)})"
            if delta.goal_months_earlier is not None
            else ""
        )
        lines.append(
            f"• {s.name}: goal reached {when}{timing}, "
            f"{eur(r.projected_value_at_target_date)} on the target date "
            f"({signed_eur(delta.value_at_target_difference)})."
        )
    return "\n".join(lines)


def _assumptions_reply(facts: Facts) -> str:
    r = facts.rates
    assert r is not None
    return (
        f"The {facts.assumption_set} assumption set uses, per year: "
        f"{percent(r.annual_return)} investment return, {percent(r.annual_salary_growth)} "
        f"salary growth and {percent(r.annual_expense_growth)} expense growth. Inflation "
        f"({percent(r.annual_inflation)}) is shown for reference but not used in the "
        f"calculations.\n\nThe projection also simplifies: {'; '.join(SIMPLIFICATIONS)}.\n\n"
        "These are assumptions you can edit, not forecasts."
    )


# ---- replies that never involve results ---------------------------------------------------------

DECLINE = {
    "advice": (
        "I can't recommend what to do or which products to choose; I only show what happens "
        "under the assumptions you set. For example, ask “What if I invest €200 more per "
        "month?” and I'll show how that changes the projection."
    ),
    "out_of_scope": (
        "That's outside what this simulator covers: it projects your savings goal from your "
        f"own figures and assumptions. You can ask things like {EXAMPLES}."
    ),
    "not_understood": f"I didn't understand that. You can ask things like {EXAMPLES}.",
}

NEEDS_PLAN = (
    "I need your plan first: your finances today and a goal. Add them on the “Your plan” "
    "page, then ask again."
)
