"""Labelled messages for evaluating intent parsers (`python -m app.agents.evaluate`).

Each case: the message, an optional previous message in the same conversation, and the
expected intent. Some phrasings are deliberately outside the rule-based parser's patterns,
so the comparison shows where a language model helps and where it doesn't.
"""

from typing import NamedTuple


class Case(NamedTuple):
    message: str
    expected: dict
    """`kind`, plus `overrides` (only the fields that must be set) and `assumption_set`."""
    previous: str | None = None


def what_if(**overrides: float) -> dict:
    return {"kind": "what_if", "overrides": overrides}


CASES: list[Case] = [
    # Plan questions
    Case("Am I on track?", {"kind": "run_projection"}),
    Case("How is my plan looking?", {"kind": "run_projection"}),
    Case("Give me an overview of where I'll be", {"kind": "run_projection"}),
    Case("When will I reach my goal?", {"kind": "goal_date"}),
    Case("By when can I afford the house?", {"kind": "goal_date"}),
    Case("How long until I get there?", {"kind": "goal_date"}),
    Case("How much do I need to invest each month?", {"kind": "required_contribution"}),
    Case("What monthly amount gets me to the target on time?", {"kind": "required_contribution"}),
    Case("Compare my options", {"kind": "compare_scenarios"}),
    Case("Show me the different scenarios", {"kind": "compare_scenarios"}),
    Case("What are you assuming?", {"kind": "explain_assumptions"}),
    Case("Which growth rates are you using?", {"kind": "explain_assumptions"}),
    # What-ifs
    Case(
        "What if I invest €200 more per month?", what_if(monthly_investment_contribution_delta=200)
    ),
    Case(
        "What if I put an extra 150 into investments monthly?",
        what_if(monthly_investment_contribution_delta=150),
    ),
    Case(
        "Suppose I invested 100 euros less each month",
        what_if(monthly_investment_contribution_delta=-100),
    ),
    Case("What if I invest €600 a month?", what_if(monthly_investment_contribution=600)),
    Case("What if I stop investing?", what_if(monthly_investment_contribution=0)),
    Case("What if I spend €200 less?", what_if(monthly_expenses_delta=-200)),
    Case("Imagine I trimmed my monthly spending by 250", what_if(monthly_expenses_delta=-250)),
    Case("What if my rent goes up by 100 a month?", what_if(monthly_expenses_delta=100)),
    Case("What if I earn €3,000 a month?", what_if(monthly_net_income=3000)),
    Case("What if I get a raise of €300?", what_if(monthly_net_income_delta=300)),
    Case("What if returns are only 3%?", what_if(annual_return=0.03)),
    Case("What if the market gives me 7% a year?", what_if(annual_return=0.07)),
    Case("What if my salary grows 4% a year?", what_if(annual_salary_growth=0.04)),
    Case(
        "What if I invest €200 more and spend €100 less?",
        what_if(monthly_investment_contribution_delta=200, monthly_expenses_delta=-100),
    ),
    # Follow-ups and assumption sets
    Case(
        "And with €300 instead?",
        what_if(monthly_investment_contribution_delta=300),
        previous="What if I invest €200 more per month?",
    ),
    Case(
        "And 4%?",
        what_if(annual_return=0.04),
        previous="What if returns are only 3%?",
    ),
    Case(
        "Am I on track under pessimistic assumptions?",
        {"kind": "run_projection", "assumption_set": "conservative"},
    ),
    Case(
        "In the optimistic case, when do I reach it?",
        {"kind": "goal_date", "assumption_set": "optimistic"},
    ),
    # Phase 2: how likely, and one-off market moves (added before tuning nothing: some
    # phrasings are deliberately outside the rules)
    Case("How likely am I to reach my goal?", {"kind": "likelihood"}),
    Case("What are the odds I make it in time?", {"kind": "likelihood"}),
    Case("Is my goal realistic?", {"kind": "likelihood"}),
    Case("What if the market falls 30% next year?", what_if(first_year_return=-0.3)),
    Case("What if we get a stock market crash of 35%?", what_if(first_year_return=-0.35)),
    Case("Suppose my ETFs lose 20% in the next twelve months", what_if(first_year_return=-0.2)),
    Case(
        "How likely is that?",
        {"kind": "likelihood", "overrides": {"first_year_return": -0.3}},
        previous="What if the market falls 30% next year?",
    ),
    Case(
        "What are my chances if I invest €100 more?",
        {"kind": "likelihood", "overrides": {"monthly_investment_contribution_delta": 100}},
    ),
    # Not answerable
    Case("Should I buy an ETF?", {"kind": "unsupported", "reason": "advice"}),
    Case("Which fund is best for me?", {"kind": "unsupported", "reason": "advice"}),
    Case("Is it smart to pay off my loan early?", {"kind": "unsupported", "reason": "advice"}),
    Case("What's the weather tomorrow?", {"kind": "unsupported"}),
    Case("How do capital gains taxes work in Ireland?", {"kind": "unsupported"}),
]


def matches(intent: dict, expected: dict) -> bool:
    """True when the parsed intent has the expected kind, reason, assumption set and exactly
    the expected overrides (unexpected extra changes count as wrong)."""
    if intent.get("kind") != expected["kind"]:
        return False
    if "reason" in expected and intent.get("reason") != expected["reason"]:
        return False
    if intent.get("assumption_set") != expected.get("assumption_set"):
        return False
    if expected["kind"] in ("what_if", "likelihood"):
        got = {k: v for k, v in (intent.get("overrides") or {}).items() if v is not None}
        return got == {k: float(v) for k, v in expected.get("overrides", {}).items()}
    return True
