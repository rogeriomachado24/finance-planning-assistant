"""A language model reads what the rules couldn't place in a plan description.

The model fills a flat form (`ModelPlanForm`), constrained by Ollama to its JSON schema. Its
answer is never trusted as is:
- every amount must be written in the message (as for the chat), and a value that fails is
  dropped rather than guessed;
- a yearly period needs year words in the message, and a month needs a month name;
- it only fills fields the rules left empty (where both answer, the rules win, as measured
  on the chat).
It never calculates: separate amounts stay separate and periods stay as written; the draft
(via the domain) adds and converts.
"""

import logging
import re
from typing import Literal

from pydantic import BaseModel, Field

from app.agents.grounding import as_number, number_tokens, numbers_in
from app.agents.plan_draft import Amount, Extraction, GoalDate, GoalShare
from app.domain.models import GoalType
from app.domain.plan_input import Period

log = logging.getLogger(__name__)

Kind = Literal[
    "house", "emergency_fund", "retirement", "education", "vehicle", "travel", "wedding", "other"
]


class ModelPlanForm(BaseModel):
    """What the model fills in. Lists keep separately written amounts apart (rent 900, food
    300); periods only when the message says them."""

    take_home_pay: list[float] | None = Field(None, description="Pay after tax, as written.")
    take_home_pay_period: Literal["month", "year"] | None = None
    other_income: list[float] | None = Field(None, description="E.g. rent received.")
    other_income_period: Literal["month", "year"] | None = None
    expenses: list[float] | None = Field(None, description="Spending, each amount as written.")
    expenses_period: Literal["month", "year"] | None = None
    cash: list[float] | None = Field(None, description="In bank or savings accounts now.")
    investments: list[float] | None = Field(None, description="Funds, ETFs, shares now.")
    monthly_investment: float | None = Field(None, description="Invested every month.")
    debt: float | None = Field(None, description="Debt still owed.")
    debt_payment_per_month: float | None = None
    age: int | None = None
    goal_amount: float | None = Field(None, description="The amount to save, if stated.")
    goal_percent_of_price: float | None = Field(None, description="E.g. 20 for '20% deposit'.")
    goal_price: float | None = Field(None, description="The price that percentage is of.")
    goal_year: int | None = None
    goal_month: int | None = Field(None, description="1-12, only if a month is named.")
    goal_in_years: int | None = None
    goal_in_months: int | None = None
    goal_kind: Kind | None = None
    keep_savings: float | None = Field(
        None, description="Savings to keep aside, not used for the goal (an emergency fund)."
    )
    keep_investments: float | None = Field(
        None, description="Investments to keep aside, not used for the goal."
    )
    dont_touch_savings: bool | None = Field(None, description="Keep all of today's savings.")
    dont_touch_investments: bool | None = Field(
        None, description="Keep all of today's investments (\"don't touch my investments\")."
    )


SYSTEM = """You copy facts about a person's finances from their message into JSON. Never answer
or give advice.

Rules:
- Copy each amount exactly as written ("8k" is 8000). Never add, multiply or convert amounts.
- Keep amounts that are written separately as separate list items: "rent 900 and food 300"
  gives expenses [900, 300].
- Give a period ("month" or "year") only if the message says it.
- take_home_pay is pay after tax. If the message says before tax or gross, leave it null.
- Leave everything that is not mentioned null."""

EXAMPLES: list[tuple[str, dict]] = [
    (
        "I bring home 2,100 a month, rent is 800 plus 400 for the rest",
        {"take_home_pay": [2100], "take_home_pay_period": "month", "expenses": [800, 400]},
    ),
    (
        "about 6k sitting in my bank and 3k in index funds, no loans",
        {"cash": [6000], "investments": [3000]},
    ),
    (
        "we're hoping for a 15% down payment on a 400k home in 5 years",
        {
            "goal_percent_of_price": 15,
            "goal_price": 400000,
            "goal_in_years": 5,
            "goal_kind": "house",
        },
    ),
]

_KINDS = {
    "house": GoalType.HOUSE,
    "emergency_fund": GoalType.EMERGENCY_FUND,
    "retirement": GoalType.RETIREMENT,
    "education": GoalType.EDUCATION,
    "vehicle": GoalType.VEHICLE,
    "travel": GoalType.TRAVEL,
    "wedding": GoalType.OTHER,
    "other": GoalType.OTHER,
}
_FLOWS = [
    ("take_home_pay", "monthly_net_income"),
    ("other_income", "other_monthly_income"),
    ("expenses", "monthly_expenses"),
]
_STOCKS = [("cash", "cash"), ("investments", "investments")]
_SINGLE = [
    ("monthly_investment", "monthly_investment_contribution", Period.MONTH),
    ("debt", "debt_balance", None),
    ("debt_payment_per_month", "monthly_debt_payment", Period.MONTH),
    ("goal_amount", "goal_target_amount", None),
    ("keep_savings", "goal_keep_savings", None),
    ("keep_investments", "goal_keep_investments", None),
]
_YEAR_WORDS = r"\b(year|yearly|annual\w*|p\.?a\.?|per annum)\b"
_MONTH_NAMES = r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b"


def to_extraction(form: ModelPlanForm, message: str) -> Extraction:
    """The model's form as an extraction, keeping only what the message supports."""
    written = numbers_in(message)

    def checked(values: list[float] | None, name: str) -> list[float] | None:
        if not values:
            return None
        if all(as_number(v) in written for v in values):
            return values
        log.info("model %s=%s dropped: not in the message", name, values)
        return None

    def period(value: str | None) -> Period | None:
        if value == "year" and not re.search(_YEAR_WORDS, message, re.I):
            return None  # a "per year" the message doesn't say
        return Period(value) if value else None

    found = Extraction()
    for name, field in _FLOWS:
        parts = checked(getattr(form, name), name)
        if parts:
            found.amounts.append(
                Amount(field=field, parts=parts, period=period(getattr(form, f"{name}_period")))  # type: ignore[arg-type]
            )
    for name, field in _STOCKS:
        if parts := checked(getattr(form, name), name):
            found.amounts.append(Amount(field=field, parts=parts))  # type: ignore[arg-type]
    for name, field, per in _SINGLE:
        value = getattr(form, name)
        if value is not None and checked([value], name):
            found.amounts.append(Amount(field=field, parts=[value], period=per))  # type: ignore[arg-type]

    if form.age is not None and checked([form.age], "age") and 0 <= form.age <= 120:
        found.age = form.age
    percent, price = form.goal_percent_of_price, form.goal_price
    if percent and price and checked([percent, price], "goal share") and 0 < percent <= 100:
        found.goal_share = GoalShare(percent=percent, price=price)
        found.amounts = [a for a in found.amounts if a.field != "goal_target_amount"]
    found.goal_date = _goal_date(form, written, message)
    found.keep_all = [  # type: ignore[assignment]
        pot
        for pot, flag in (
            ("savings", form.dont_touch_savings),
            ("investments", form.dont_touch_investments),
        )
        if flag
    ]
    if form.goal_kind:
        found.goal_type = _KINDS[form.goal_kind]
        if form.goal_kind == "wedding":
            found.goal_name = "Wedding"
    return found


def _goal_date(form: ModelPlanForm, written: set, message: str) -> GoalDate | None:
    for n, key in ((form.goal_in_years, "in_years"), (form.goal_in_months, "in_months")):
        if n and as_number(n) in written and 0 < n <= (50 if key == "in_years" else 600):
            return GoalDate(**{key: n})
    if form.goal_year and as_number(form.goal_year) in written and 1900 <= form.goal_year <= 2200:
        month = form.goal_month if re.search(_MONTH_NAMES, message, re.I) else None
        return GoalDate(year=form.goal_year, month=month if month and 1 <= month <= 12 else None)
    return None


def rules_missed_something(message: str, found: Extraction) -> bool:
    """True when the message has a number the rules didn't use, or the rules understood
    nothing in a message of a few words: the cases worth asking the model about."""
    used = {as_number(p) for a in found.amounts for p in a.parts}
    if found.age is not None:
        used.add(as_number(found.age))
    if found.goal_share:
        used |= {as_number(found.goal_share.percent), as_number(found.goal_share.price)}
    if d := found.goal_date:
        used |= {as_number(v) for v in (d.year, d.in_years, d.in_months) if v}
    unexplained = [t for t in number_tokens(message) if not t & used]
    understood_nothing = (
        not (found.amounts or found.zeros or found.age or found.goal_type or found.goal_date)
        and found.answer is None
    )
    return bool(unexplained) or (understood_nothing and len(message.split()) >= 3)


def merge(rules: Extraction, model: Extraction) -> Extraction:
    """The rules' extraction, with the model's values for whatever the rules left empty."""
    merged = rules.model_copy(deep=True)
    have = {a.field for a in rules.amounts} | set(rules.zeros)
    if rules.goal_share:
        have.add("goal_target_amount")
    merged.amounts += [a for a in model.amounts if a.field not in have]
    merged.keep_all = [*merged.keep_all, *(p for p in model.keep_all if p not in merged.keep_all)]
    for name in ("age", "goal_date", "goal_type", "goal_name"):
        if getattr(merged, name) is None:
            setattr(merged, name, getattr(model, name))
    if merged.goal_share is None and "goal_target_amount" not in have:
        merged.goal_share = model.goal_share
        if merged.goal_share:
            merged.amounts = [a for a in merged.amounts if a.field != "goal_target_amount"]
    # Mark what the model contributed, so the draft asks the person to check it.
    merged.from_model = [a.field for a in merged.amounts if a.field not in have]
    for name, field in (("age", "age"), ("goal_date", "goal_target_date")):
        if getattr(rules, name) is None and getattr(model, name) is not None:
            merged.from_model.append(field)
    return merged
