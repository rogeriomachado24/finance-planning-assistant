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
    RequiredContribution,
    RunProjection,
    WhatIf,
)
from app.schemas.plan import Rates
from app.schemas.scenarios import ComparedScenarioOut, OverridesIn, ScenarioResultOut

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
    "month?”, “What if I invest €200 more per month?”, “Compare my options”"
)

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


@dataclass(frozen=True)
class Facts:
    """Everything an explanation may use: the request and the engine's rounded results."""

    intent: Intent
    results: list[ComparedScenarioOut]
    assumption_set: str | None
    rates: Rates | None
    question: str = ""


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


def duration(months: int) -> str:
    years, rest = divmod(months, 12)
    parts = []
    if years:
        parts.append(f"{years} year{'s' if years != 1 else ''}")
    if rest or not years:
        parts.append(f"{rest} month{'s' if rest != 1 else ''}")
    return " ".join(parts)


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
    if isinstance(intent, WhatIf):
        body = _what_if(facts.results, intent.overrides)
    elif isinstance(intent, CompareScenarios):
        body = _comparison(facts.results)
    elif isinstance(intent, RequiredContribution):
        body = _required(current)
    elif isinstance(intent, GoalDate | RunProjection):
        body = _goal_sentence(current)
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


def _goal_sentence(r: ScenarioResultOut) -> str:
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
    return text


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
            f" ({months_earlier(delta.goal_months_earlier).replace(' than', '')})"
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
