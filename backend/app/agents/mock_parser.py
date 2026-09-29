"""Rule-based intent parser: the mock provider, and the fallback when no model is available.

It recognises a fixed set of English phrasings. It never calculates: amounts are copied
from the message (percentages are only converted to decimals, a change of unit), and
"spend €200 less" becomes a delta of -200 for the engine to apply.
"""

import re

from app.agents.intents import (
    CompareScenarios,
    ExplainAssumptions,
    GoalDate,
    Intent,
    NeedsClarification,
    RequiredContribution,
    RunProjection,
    Unsupported,
    WhatIf,
)
from app.schemas.scenarios import OverridesIn

# Money: "€200", "200 euros", "1,500", "1.5k". A number followed by % is a rate, not money.
_AMOUNT = re.compile(
    r"(?<![\w.])(?P<num>\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s?(?P<k>k\b)?"
    r"(?!\s?%|\s?percent|\s?per cent|\d)"
)
# A year after "in/by/until/before/after" is a date: "by 2030" is not €2,030.
_YEAR = re.compile(r"\b(in|by|until|before|after) (19|20)\d\d\b")
_PERCENT = re.compile(r"(?P<num>\d+(?:\.\d+)?)\s?(?:%|percent|per cent)")

_MONEY_FIELDS = [
    (
        "monthly_investment_contribution",
        r"\b(invest\w*|contribut\w*|put (?:in|away|aside)|sav(?:e|ing)|set aside)\b",
    ),
    ("monthly_net_income", r"\b(earn\w*|salary|income|take[- ]home|paid|raise|pay rise)\b"),
    ("monthly_expenses", r"\b(spend\w*|expenses?|costs?|cut\w*|living)\b"),
]
_RATE_FIELDS = [  # most specific first: "salary grows 3%" is not an investment return
    (
        "annual_salary_growth",
        r"\b(salary|salaries|pay|income|wages?)\b.*\b(grow\w*|ris\w*|increas\w*)\b|salary growth",
    ),
    (
        "annual_expense_growth",
        r"\b(expenses?|costs?|spending)\b.*\b(grow\w*|ris\w*|increas\w*)\b|expense growth",
    ),
    ("annual_return", r"\b(returns?|yield\w*|grow\w*|performance|market|interest)\b"),
]
_LESS = r"\b(less|fewer|lower|reduc\w*|cut\w*|drop\w*|decreas\w*|minus)\b"
_MORE = r"\b(more|extra|additional|another|increas\w*|raise|rise|higher|plus|on top)\b"

_SETS = [
    ("conservative", r"\b(conservative|pessimistic|cautious|worst)\b"),
    ("optimistic", r"\b(optimistic|best case|hopeful)\b"),
    ("base", r"\bbase\b"),
]

_REQUIRED = (
    r"how much (do|would|will|should|must) i (need to|have to|) ?(save|invest|put|set aside)"
    r"|required (monthly )?contribution|needed per month|need(ed)? each month"
    r"|how much .* (per|a|each|every) month .* (reach|get|goal|on time|in time)"
)
_ADVICE = (
    r"\b(should i|shall i|do you recommend|recommend\w*|advice|advise|what should"
    r"|is it (a )?good (idea|time)|worth it)\b"
    r"|\b(which|what|best|good)\b.*\b(stocks?|etfs?|funds?|crypto|bitcoin|shares|bonds?|broker)\b"
    r"|\b(buy|sell)\b.*\b(stocks?|etfs?|funds?|crypto|bitcoin|shares|bonds?)\b"
)
_OUT_OF_SCOPE = (
    r"\b(tax\w*|mortgage|news|weather|stock market today|interest rates? today|loan offers?)\b"
)
_COMPARE = r"\b(compar\w*|scenarios?|options|levers|alternatives|side by side)\b"
_GOAL_DATE = (
    r"\bwhen\b.*\b(reach|hit|get|achieve|afford|there|done|goal)\b|how long|goal date|what date"
)
# Questions about the assumptions, not "am I on track under pessimistic assumptions?".
_ASSUMPTIONS = (
    r"\b(what|which|explain|show|list|tell me)\b.*\bassum\w*|\bwhat rates\b|\bwhich rates\b"
    r"|\bwhat return\b"
)
_PROJECTION = (
    r"on track|projection|\bproject\b|where will i be|how am i doing|my plan|\bstatus\b"
    r"|overview|summary"
)
_WHAT_IF = (
    r"\bwhat if\b|\bif i\b|\bsuppose\b|\bimagine\b|\binstead\b|\bhow about\b|\band with\b"
    r"|\bwhat about\b"
)
# "And under conservative assumptions?": the previous question again, with another set.
_RERUN = r"^(and\b|what about\b|how about\b|under\b|with\b|using\b)|\binstead\b"


def parse_message(message: str, previous: Intent | None = None) -> Intent:
    text = _normalise(message)
    assumption_set = next((name for name, pattern in _SETS if re.search(pattern, text)), None)

    if re.search(_REQUIRED, text):
        return RequiredContribution(assumption_set=assumption_set)
    if re.search(_ADVICE, text):
        return Unsupported(reason="advice")

    overrides, clarification = _extract_overrides(text, previous)
    if overrides:
        return WhatIf(overrides=OverridesIn(**overrides), assumption_set=assumption_set)
    if clarification:
        return NeedsClarification(question=clarification)

    rerunnable = (RunProjection, GoalDate, RequiredContribution, WhatIf, CompareScenarios)
    if assumption_set and isinstance(previous, rerunnable) and re.search(_RERUN, text):
        return previous.model_copy(update={"assumption_set": assumption_set})

    for pattern, intent in (
        (_COMPARE, CompareScenarios),
        (_GOAL_DATE, GoalDate),
        (_ASSUMPTIONS, ExplainAssumptions),
        (_PROJECTION, RunProjection),
    ):
        if re.search(pattern, text):
            return intent(assumption_set=assumption_set)

    if re.search(_OUT_OF_SCOPE, text):
        return Unsupported(reason="out_of_scope")
    return Unsupported(reason="not_understood")


def _normalise(message: str) -> str:
    text = message.lower().replace("’", "'").replace("€ ", "€")
    return re.sub(r"\s+", " ", text).strip()


def _extract_overrides(text: str, previous: Intent | None) -> tuple[dict[str, float], str | None]:
    """Changes mentioned in the message, clause by clause ("invest 200 more and spend 100
    less"). Returns the overrides, or a clarifying question when a number can't be placed."""
    overrides: dict[str, float] = {}
    unplaced: str | None = None
    is_what_if = bool(re.search(_WHAT_IF, text))

    # Split on "and", ";" and commas, but not the comma in "1,500".
    for clause in re.split(r"\band\b|,(?!\d)|;", text):
        if re.search(r"\bstop (investing|contributing|saving)\b", clause):
            overrides["monthly_investment_contribution"] = 0
            continue
        if percent := _PERCENT.search(clause):
            rate = round(float(percent["num"]) / 100, 6)
            if field := _match_field(clause, _RATE_FIELDS):
                overrides[field] = rate
            elif follow_up := _follow_up(previous, rate=True):
                overrides[follow_up[0]] = rate
            else:
                unplaced = (
                    f"Should {percent['num']}% be the investment return, the salary growth or "
                    "the expense growth? For example: 'what if returns are 3% a year?'"
                )
            continue
        amount = _parse_amount(clause)
        if amount is None:
            continue
        if field := _match_field(clause, _MONEY_FIELDS):
            overrides.update(_money_override(field, clause, amount))
        elif follow_up := _follow_up(previous, rate=False):
            name, old_value = follow_up
            overrides[name] = (
                _signed(clause, amount, old_value) if name.endswith("_delta") else amount
            )
        elif is_what_if or re.search(f"{_MORE}|{_LESS}", clause):
            unplaced = (
                f"Should €{amount:,.0f} change your monthly investment, your take-home pay or "
                "your expenses? For example: 'what if I invest €200 more per month?'"
            )

    return overrides, None if overrides else unplaced


def _parse_amount(clause: str) -> float | None:
    match = _AMOUNT.search(_YEAR.sub(" ", clause))
    if not match:
        return None
    value = float(match["num"].replace(",", ""))
    return value * 1000 if match["k"] else value


def _match_field(clause: str, fields: list[tuple[str, str]]) -> str | None:
    return next((name for name, pattern in fields if re.search(pattern, clause)), None)


def _money_override(field: str, clause: str, amount: float) -> dict[str, float]:
    """'spend 200 less' -> delta -200; 'invest 200 more' -> delta +200; 'earn 3,000' -> 3000."""
    if re.search(_LESS, clause) or re.search(_MORE, clause):
        return {f"{field}_delta": _signed(clause, amount, previous_value=amount)}
    return {field: amount}


def _signed(clause: str, amount: float, previous_value: float) -> float:
    """A delta's sign: from "more"/"less" in the clause, otherwise the previous delta's."""
    if re.search(_LESS, clause):
        return -amount
    if re.search(_MORE, clause):
        return amount
    return amount if previous_value >= 0 else -amount


def _follow_up(previous: Intent | None, *, rate: bool) -> tuple[str, float] | None:
    """'And with €300 instead?' reuses the one field the previous what-if changed, and
    returns it with its previous value."""
    if not isinstance(previous, WhatIf):
        return None
    changed = [(k, v) for k, v in previous.overrides.model_dump().items() if v is not None]
    if len(changed) != 1:
        return None
    name, value = changed[0]
    return changed[0] if name.startswith("annual_") == rate else None
