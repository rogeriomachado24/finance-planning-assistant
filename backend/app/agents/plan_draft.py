"""Describe your plan (docs/PHASE3_DESIGN.md, section 2): the draft, how an extraction updates
it, and which question comes next.

An `Extraction` is what the person wrote: amounts copied from the message, with their parts
and period. Applying it to the draft is deterministic, and every calculation (adding parts,
yearly to monthly, a percentage of a price, "in 6 years") is done by the domain and shown in
the draft's notes. Nothing here saves anything: the person checks the forms and saves them.
"""

from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from app.agents.explain import day, eur
from app.domain.models import GoalType
from app.domain.plan_input import Period, months_from_now, per_month, share_of, total

FlowField = Literal[
    "monthly_net_income",
    "other_monthly_income",
    "monthly_expenses",
    "monthly_investment_contribution",
    "monthly_debt_payment",
]
StockField = Literal[
    "cash",
    "investments",
    "debt_balance",
    "goal_target_amount",
    "goal_keep_savings",
    "goal_keep_investments",
]
AmountField = FlowField | StockField
FLOW_FIELDS: tuple[str, ...] = FlowField.__args__  # type: ignore[attr-defined]

LABELS = {
    "monthly_net_income": "Take-home pay",
    "other_monthly_income": "Other income",
    "monthly_expenses": "Expenses",
    "cash": "Cash",
    "investments": "Investments",
    "monthly_investment_contribution": "Monthly investment",
    "debt_balance": "Debt",
    "monthly_debt_payment": "Debt payment",
    "age": "Age",
    "goal_name": "Goal name",
    "goal_target_amount": "Goal amount",
    "goal_keep_savings": "Kept aside from savings",
    "goal_keep_investments": "Kept aside from investments",
    "goal_target_date": "Goal date",
}

DEFAULT_GOAL_NAMES = {
    GoalType.HOUSE: "Buy a house",
    GoalType.EMERGENCY_FUND: "Emergency fund",
    GoalType.RETIREMENT: "Retirement",
    GoalType.EDUCATION: "Education",
    GoalType.VEHICLE: "Buy a car",
    GoalType.TRAVEL: "Travel",
}


class Amount(BaseModel):
    """One amount as described: "rent 900 and 700 for everything else" is one amount for
    `monthly_expenses` with parts [900, 700]."""

    field: AmountField
    parts: list[float] = Field(min_length=1, description="Each number as written.")
    period: Period | None = Field(None, description="For monthly amounts: as written, if at all.")


class GoalDate(BaseModel):
    """ "By June 2032" -> year 2032, month 6; "in 6 years" -> in_years 6."""

    year: int | None = Field(None, ge=1900, le=2200)
    month: int | None = Field(None, ge=1, le=12)
    in_years: int | None = Field(None, gt=0, le=50)
    in_months: int | None = Field(None, gt=0, le=600)


class GoalShare(BaseModel):
    """ "A 20% deposit on a 300k house": a goal amount to confirm, worked out by the domain."""

    percent: float = Field(gt=0, le=100)
    price: float = Field(gt=0)


class Answer(StrEnum):
    """A short reply to the question asked."""

    YES = "yes"
    NO = "no"
    SKIP = "skip"


ZeroableField = Literal[
    "cash",
    "investments",
    "monthly_investment_contribution",
    "debt_balance",
    "other_monthly_income",
]


class Extraction(BaseModel):
    """What one message said. Produced by rules or by a language model; never calculated."""

    amounts: list[Amount] = []
    zeros: list[ZeroableField] = Field(
        [], description='Said to be nothing: "no debt", "I don\'t invest yet".'
    )
    age: int | None = Field(None, ge=0, le=120)
    goal_type: GoalType | None = None
    goal_name: str | None = Field(None, max_length=100)
    goal_date: GoalDate | None = None
    goal_share: GoalShare | None = None
    answer: Answer | None = None
    keep_all: list[Literal["savings", "investments"]] = Field(
        [], description="\"Don't touch my investments\": keep all of today's pot aside."
    )
    from_model: list[str] = Field(
        [], description="Fields a language model read (not the rules): shown for review."
    )


class PlanDraft(BaseModel):
    """The forms' values so far. Sent back by the browser with each message (the API keeps
    nothing). None means "not known yet"; 0 means "said to be nothing"."""

    monthly_net_income: float | None = None
    other_monthly_income: float | None = None
    monthly_expenses: float | None = None
    cash: float | None = None
    investments: float | None = None
    monthly_investment_contribution: float | None = None
    debt_balance: float | None = None
    monthly_debt_payment: float | None = None
    age: int | None = None
    goal_name: str | None = None
    goal_type: GoalType | None = None
    goal_target_amount: float | None = None
    goal_target_date: date | None = None
    goal_keep_savings: float | None = None
    goal_keep_investments: float | None = None
    keep_all: list[str] = Field(
        [], description="Pots to keep aside in full, waiting for their amount."
    )
    notes: dict[str, str] = Field({}, description='How a value was worked out: "€900 + €700".')
    skipped: list[str] = []
    asked: str | None = Field(None, description="The field the last question was about.")
    to_check: list[str] = Field(
        [], description="Fields read by a language model, to be checked before saving."
    )
    pending_goal_amount: float | None = Field(
        None, description="A goal amount worked out from a percentage, waiting for a yes."
    )


REQUIRED = (
    "monthly_net_income",
    "monthly_expenses",
    "goal_target_amount",
    "goal_target_date",
    "goal_name",
)
"""Needed before the forms can be saved."""
OPTIONAL_ASKED = (
    "cash",
    "investments",
    "monthly_investment_contribution",
    "debt_balance",
    "monthly_debt_payment",
)
"""Asked about once (they default to 0), but never required."""

QUESTIONS = {
    "monthly_net_income": "How much do you take home each month, after tax?",
    "monthly_expenses": "Roughly how much do you spend each month, not counting debt payments?",
    "goal_target_amount": "How much do you want to save for your goal?",
    "goal_target_date": "By when? For example “June 2032” or “in 6 years”.",
    "goal_name": "What should the goal be called? For example “House deposit”.",
    "cash": "How much do you have in cash or savings accounts today? If nothing, say 0.",
    "investments": "And in investments, such as funds or ETFs? If nothing, say 0.",
    "monthly_investment_contribution": "How much do you invest each month? If nothing yet, say 0.",
    "debt_balance": "Do you have any debt, such as a loan? Say how much, or no.",
    "monthly_debt_payment": "How much do you pay on that debt each month?",
}
DONE = "That's everything. Check the forms below and save them; you can change any field."


class DraftReply(BaseModel):
    draft: PlanDraft
    understood: list[str] = Field(description="What this message changed, in words.")
    question: str
    """The next question, or a note that everything needed is there."""
    still_missing: list[str] = Field(description="Required fields not filled yet.")
    optional_missing: list[str] = Field(description="Optional fields not answered yet.")
    complete: bool = Field(description="Every required field is filled.")


def apply_extraction(draft: PlanDraft, found: Extraction, today: date) -> DraftReply:
    """Update the draft with what one message said, and choose the next question."""
    d = draft.model_copy(deep=True)
    understood: list[str] = []

    def put(field: str, value: float | int | str | date, note: str | None, line: str) -> None:
        setattr(d, field, value)
        d.notes.pop(field, None)
        if note:
            d.notes[field] = note
        if field in d.skipped:
            d.skipped.remove(field)
        if field in d.to_check:
            d.to_check.remove(field)
        if field in found.from_model:
            d.to_check.append(field)
            line += " · read by the AI, please check"
        understood.append(line)

    # A goal amount worked out from a percentage waits for a yes (or another amount).
    if d.pending_goal_amount is not None:
        if found.answer is Answer.YES:
            put(
                "goal_target_amount",
                d.pending_goal_amount,
                d.notes.get("pending"),
                f"Goal amount: {eur(d.pending_goal_amount)} ({d.notes.get('pending')})",
            )
        d.pending_goal_amount = None
        d.notes.pop("pending", None)

    for amount in found.amounts:
        value, note = _amount_value(amount)
        per = " a month" if amount.field in FLOW_FIELDS else ""
        line = f"{LABELS[amount.field]}: {eur(value)}{per}" + (f" ({note})" if note else "")
        put(amount.field, value, note, line)

    for field in found.zeros:
        put(field, 0.0, None, f"{LABELS[field]}: none")

    if found.goal_share is not None:
        s = found.goal_share
        d.pending_goal_amount = share_of(s.percent, s.price)
        d.notes["pending"] = f"{_number(s.percent)}% of {eur(s.price)}"

    if found.goal_date is not None:
        resolved = _goal_date(found.goal_date, today)
        if resolved is not None:
            when, note = resolved
            line = f"Goal date: {day(when)}" + (f" ({note})" if note else "")
            put("goal_target_date", when, note, line)

    if found.goal_type is not None:
        d.goal_type = found.goal_type
        if (
            found.goal_name is None
            and d.goal_name is None
            and found.goal_type in DEFAULT_GOAL_NAMES
        ):
            name = DEFAULT_GOAL_NAMES[found.goal_type]
            put("goal_name", name, None, f"Goal: {name}")
    if found.goal_name:
        put("goal_name", found.goal_name, None, f"Goal: {found.goal_name}")

    if found.age is not None:
        put("age", found.age, None, f"Age: {found.age}")

    # "Don't touch my investments": all of today's pot, once its amount is known (copied).
    # It follows that amount if it changes later; an amount said for the pot replaces it.
    said = {a.field for a in found.amounts}
    for pot in found.keep_all:
        if pot not in d.keep_all and f"goal_keep_{pot}" not in said:
            d.keep_all.append(pot)
    for pot in list(d.keep_all):
        field = f"goal_keep_{pot}"
        amount = d.cash if pot == "savings" else d.investments
        note = f"all of today's {pot}"
        if field in said:
            d.keep_all.remove(pot)
        elif amount is None and pot in found.keep_all:
            understood.append(f"{LABELS[field]}: {note} (once that amount is known)")
        elif amount is not None and getattr(d, field) != amount:
            put(field, amount, note, f"{LABELS[field]}: {eur(amount)} ({note})")

    # A short answer to the question asked: "no" means nothing, "skip" leaves it empty.
    asked = draft.asked
    if asked and getattr(d, asked, None) is None and draft.pending_goal_amount is None:
        if found.answer is Answer.NO and asked in ZeroableField.__args__:  # type: ignore[attr-defined]
            put(asked, 0.0, None, f"{LABELS[asked]}: none")
        elif found.answer is Answer.SKIP and asked not in d.skipped:
            d.skipped.append(asked)
            understood.append(f"{LABELS[asked]}: skipped")

    return _reply(d, understood)


def start(draft: PlanDraft | None = None) -> DraftReply:
    """The next question for a draft as it is (the first one for an empty draft)."""
    return _reply((draft or PlanDraft()).model_copy(deep=True), [])


def _reply(d: PlanDraft, understood: list[str]) -> DraftReply:
    field, question = _next_question(d)
    d.asked = field
    missing = [LABELS[f] for f in REQUIRED if getattr(d, f) is None]
    optional = [
        LABELS[f] for f in OPTIONAL_ASKED if _still_open(d, f) and f != "monthly_debt_payment"
    ]
    return DraftReply(
        draft=d,
        understood=understood,
        question=question,
        still_missing=missing,
        optional_missing=optional,
        complete=not missing,
    )


def _still_open(d: PlanDraft, field: str) -> bool:
    if getattr(d, field) is not None or field in d.skipped:
        return False
    if field == "monthly_debt_payment":
        return bool(d.debt_balance)  # only asked when there is debt
    return True


def _next_question(d: PlanDraft) -> tuple[str | None, str]:
    if d.pending_goal_amount is not None:
        worked_out = d.notes.get("pending", "")
        return (
            "goal_target_amount",
            f"So the goal is {eur(d.pending_goal_amount)} ({worked_out})? Say yes, or give the "
            "amount.",
        )
    for field in REQUIRED + OPTIONAL_ASKED:
        if field in REQUIRED and getattr(d, field) is None and field not in d.skipped:
            return field, QUESTIONS[field]
        if field in OPTIONAL_ASKED and _still_open(d, field):
            return field, QUESTIONS[field]
    return None, DONE


def _amount_value(amount: Amount) -> tuple[float, str | None]:
    """The amount's value and how it was worked out, e.g. (1600, "€900 + €700")."""
    whole = total(amount.parts)
    shown = " + ".join(eur(p) for p in amount.parts) if len(amount.parts) > 1 else None
    if amount.field not in FLOW_FIELDS:
        return whole, shown
    if amount.period is Period.YEAR:
        return per_month(whole, Period.YEAR), f"{shown or eur(whole)} a year ÷ 12"
    if amount.period is None:
        return whole, f"{shown + ', ' if shown else ''}taken as per month"
    return whole, shown


def _goal_date(spec: GoalDate, today: date) -> tuple[date, str | None] | None:
    if spec.in_years or spec.in_months:
        months = spec.in_months or 12 * (spec.in_years or 0)
        when = months_from_now(today, months)
        unit = f"{spec.in_years} years" if spec.in_years else f"{spec.in_months} months"
        return when, f"{unit} from now"
    if spec.year:
        if spec.month:
            return date(spec.year, spec.month, 1), None
        return date(spec.year, 1, 1), "no month given, so 1 January"
    return None


def _number(value: float) -> str:
    return f"{value:g}"
