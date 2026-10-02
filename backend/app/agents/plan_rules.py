"""Rule-based reading of a plan description: the mock provider, and the first pass before a
language model (the same "rules first" strategy as the chat).

It splits the message into clauses ("I take home 2,400 a month, spend about 1,600, and have
8k saved"), recognises what each clause is about from its words, and copies the numbers in
it. It never calculates: "rent 900 and 700 for everything else" becomes one amount with two
parts, and "36k a year" keeps its period; the draft (via the domain) does the arithmetic.
"""

import re

from app.agents.mock_parser import INVESTMENT_POT, KEEP_VERB, SAVINGS_POT
from app.agents.plan_draft import (
    FLOW_FIELDS,
    Amount,
    Answer,
    Extraction,
    GoalDate,
    GoalShare,
)
from app.domain.models import GoalType
from app.domain.plan_input import Period

# ---- numbers --------------------------------------------------------------------------------

# "2,400", "8.000" (thousands), "1.5k", "€60k", "300 thousand", "1.2m". Not "20%".
_AMOUNT = re.compile(
    r"(?<![\w.,])€?\s?(?P<num>\d{1,3}(?:[,.]\d{3})+(?!\d)|\d+(?:\.\d+)?)"
    r"\s?(?P<unit>k\b|thousand\b|m\b|million\b)?(?:\s?(?:€|euros?\b|eur\b))?"
    r"(?!\s?%|\s?percent|\s?per cent|\d|[,.]\d)"  # never part of a longer number or a "20%"
)
_PERCENT = re.compile(r"(?P<num>\d+(?:\.\d+)?)\s?(?:%|percent|per cent)")
_MONTHS = {
    m: i + 1
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    )
}
_MONTH_NAME = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*"
# Dates and ages are read first and removed, so "by 2032" or "I'm 32" never become euros.
_DATE_YEAR = re.compile(
    rf"\b(?:by|in|until|before|around|for|end of|start of|early|late)?\s*"
    rf"(?:(?:the )?(?:end|start|beginning) of )?(?:{_MONTH_NAME}\s+)?(?P<year>(?:19|20)\d\d)\b"
)
_DATE_IN = re.compile(r"\b(?:in|within)\s+(?P<n>\d{1,3})\s+(?P<unit>years?|months?)\b")
_AGE = re.compile(
    r"\b(?:i'?m|i am|aged?)\s+(?P<a>\d{2})\b(?!\s?(?:k\b|%|€|euros?|thousand|years? (?:of|in)))"
    r"|\b(?P<b>\d{2})\s?(?:years? old|y/?o)\b"
)

# ---- what a clause is about -----------------------------------------------------------------

_PER_MONTH = r"\b(?:a|per|each|every) month\b|\bmonthly\b|/\s?month\b|\bp/?m\b|\b(?:a|per) mo\b"
_PER_YEAR = r"\b(?:a|per|each|every) year\b|\byearly\b|\bannual(?:ly)?\b|/\s?year\b|\bp\.?a\.?\b"

_GOAL_VERB = (
    r"\b(want|need|would like|'d like|hope|hoping|plan|planning|aim|aiming|goal|target|dream"
    r"|save up|saving up|save for|saving for|put together)\b"
)
_GOAL_TYPES = [
    (GoalType.EMERGENCY_FUND, r"\bemergency fund\b|\brainy day\b|\bsafety net\b"),
    (
        GoalType.HOUSE,
        r"\b(house|flat|apartment|property|mortgage deposit)\b|(?<!take )(?<!take-)\bhome\b",
    ),
    (GoalType.VEHICLE, r"\b(car|vehicle|motorbike|motorcycle)\b"),
    (GoalType.TRAVEL, r"\b(trip|travel\w*|holiday|vacation|sabbatical)\b"),
    (GoalType.RETIREMENT, r"\bretire\w*\b"),
    (GoalType.EDUCATION, r"\b(university|college|degree|master'?s|course|tuition|education)\b"),
    (GoalType.OTHER, r"\bwedding\b"),
]
_HAVE = r"\b(have|having|got|saved|sitting|there'?s|i keep|kept)\b"

# Order matters: the first match decides ("rental income" is other income, not income).
_FIELDS: list[tuple[str, str]] = [
    ("debt", r"\b(debt|loans?|owe|owing|credit card|overdraft|car finance)\b"),
    (
        "monthly_investment_contribution",
        r"\b(invest|investing|put|putting|add|adding|contribut\w*|transfer\w*|move|moving)\b"
        r"(?=.*(?:" + _PER_MONTH + r"))",
    ),
    (
        "investments",
        r"\b(invest(?:ed|ments?)|etfs?|stocks?|shares|funds?|portfolio|brokerage|crypto)\b",
    ),
    (
        "cash",
        r"\b(saved|savings?|in the bank|bank account|cash|current account|deposit account"
        r"|emergency fund)\b",
    ),
    (
        "other_monthly_income",
        r"\b(rental income|rent (?:from|coming in)|side (?:income|job|hustle)|freelanc\w*"
        r"|other income|extra income|tenants?)\b",
    ),
    (
        "monthly_net_income",
        r"\b(take[- ]?home|earn\w*|salary|income|net|paid|make|making|wages?|after tax"
        r"|paycheck|payslip)\b",
    ),
    (
        "monthly_expenses",
        r"\b(spend\w*|spent|expenses?|costs?|rent|bills?|groceries|living|live on|outgoings"
        r"|food|utilities|everything else|the rest|other stuff)\b",
    ),
]

_YES = r"^(yes|yeah|yep|yup|correct|right|exactly|sure|ok|okay|that'?s right)\b"
_NO = r"^(no|nope|none|nothing|not yet|zero|i don'?t|i do not|nada)\b"
_SKIP = r"\b(skip|don'?t know|dont know|not sure|no idea|later|pass)\b"
_ZEROS: list[tuple[str, str]] = [
    ("debt_balance", r"\bno (?:debts?|loans?)\b|\bdebt[- ]free\b|\bdon'?t (?:have|owe) any debt"),
    ("monthly_investment_contribution", r"\bdon'?t invest\b|\bnot investing\b"),
    ("investments", r"\bno investments\b|\bnothing invested\b"),
    ("cash", r"\bno savings\b|\bnothing saved\b"),
]


def extract_rules(message: str, asked: str | None = None) -> Extraction:
    """What the message says, as far as the rules can tell. `asked` is the field the last
    question was about, so a bare "300" or "no" can be placed."""
    text = _normalise(message)
    found = Extraction()

    if re.search(_SKIP, text) and asked:
        found.answer = Answer.SKIP
    elif re.search(_YES, text):
        found.answer = Answer.YES
    elif re.search(_NO, text):
        found.answer = Answer.NO

    if age := _AGE.search(text):
        found.age = int(age["a"] or age["b"])
        text = text[: age.start()] + " " + text[age.end() :]

    found.goal_date, text = _goal_date(text)  # first, so "in 6 years" isn't read as €6
    clauses = _clauses(text)
    # "I want to keep 5k as an emergency fund" is money kept aside, not the goal.
    goal_text = " ".join(c for c in clauses if _is_goal_clause(c) and not _kept_pot(c))
    found.keep_all = [  # type: ignore[assignment]
        pot for c in clauses if (pot := _kept_pot(c)) and not _AMOUNT.search(c)
    ]
    found.goal_type = next((t for t, p in _GOAL_TYPES if re.search(p, goal_text)), None)
    if found.goal_type is GoalType.OTHER:
        found.goal_name = "Wedding"
    elif found.goal_type is GoalType.HOUSE and re.search(r"\bdeposit\b", goal_text):
        found.goal_name = "House deposit"
    # The answer to "What should the goal be called?" is the name, in the person's words.
    if asked == "goal_name" and not _AMOUNT.search(text):
        found.goal_name = message.strip().strip("\"'“”.")[:100] or None
        found.goal_type = found.goal_type or next(
            (t for t, p in _GOAL_TYPES if re.search(p, text)), None
        )

    found.zeros = [f for f, p in _ZEROS if re.search(p, text)]  # type: ignore[misc]
    found.amounts = _amounts(text, asked)
    for a in found.amounts:  # an amount said for a field outranks "none" in the same message
        if a.field in found.zeros:
            found.zeros.remove(a.field)  # type: ignore[arg-type]

    if share := _goal_share(goal_text):
        found.goal_share = share
        found.amounts = [a for a in found.amounts if a.field != "goal_target_amount"]
    return found


def _normalise(message: str) -> str:
    text = message.lower().replace("’", "'").replace("€ ", "€")
    return re.sub(r"\s+", " ", text).strip()


def _clauses(text: str) -> list[str]:
    """Sentences, then clauses: on commas (not in "2,400"), "and", "but", "plus"."""
    sentences = re.split(r"(?<!\d)[.!?;\n]+|[.!?;](?=\s|$)", text)
    return [
        c.strip()
        for s in sentences
        for c in re.split(r",(?!\d{3})|\band\b|\bbut\b|\bplus\b|\balso\b", s)
        if c.strip()
    ]


def _is_goal_clause(clause: str) -> bool:
    if re.search(_PER_MONTH, clause) or re.search(_PER_YEAR, clause):
        return False  # "I need 1,600 a month to live" is about spending
    if re.search(_GOAL_VERB, clause):
        return True
    has_type = any(re.search(p, clause) for _, p in _GOAL_TYPES)
    return has_type and bool(re.search(r"\bfor\b", clause)) and not re.search(_HAVE, clause)


_HOLDING = r"\bi (?:usually |always |currently )?keep\b"
_ASIDE = r"\b(aside|emergenc\w*|rainy day|untouched|separate|safety net|buffer)\b"


def _kept_pot(clause: str) -> str | None:
    """Which pot a clause keeps aside: "keep 5k as an emergency fund" -> savings, "don't touch
    my investments" -> investments; None when it isn't about keeping money aside."""
    if not re.search(KEEP_VERB, clause):
        return None
    if re.search(_HOLDING, clause) and not re.search(_ASIDE, clause):
        return None  # "I keep 10k in my savings account" says what there is
    if re.search(SAVINGS_POT, clause):
        return "savings"
    if re.search(INVESTMENT_POT, clause):
        return "investments"
    return None


def _goal_date(text: str) -> tuple[GoalDate | None, str]:
    """The first date-like phrase, removed from the text so its numbers aren't amounts."""
    if m := _DATE_IN.search(text):
        n, unit = int(m["n"]), m["unit"]
        spec = GoalDate(in_years=n) if unit.startswith("year") else GoalDate(in_months=n)
        return spec, text[: m.start()] + " " + text[m.end() :]
    if m := _DATE_YEAR.search(text):
        month_name = re.search(_MONTH_NAME, m.group(0))
        month = _MONTHS[month_name.group(1)] if month_name else None
        spec = GoalDate(year=int(m["year"]), month=month)
        return spec, text[: m.start()] + " " + text[m.end() :]
    return None, text


def _goal_share(goal_text: str) -> GoalShare | None:
    """'A 20% deposit on a 300k house': the percentage and the price, both as written."""
    percent = _PERCENT.search(goal_text)
    if not percent:
        return None
    prices = [_value(m) for m in _AMOUNT.finditer(goal_text)]
    if len(prices) != 1 or not 0 < float(percent["num"]) <= 100:
        return None
    return GoalShare(percent=float(percent["num"]), price=prices[0])


def _period(clause: str) -> Period | None:
    if re.search(_PER_MONTH, clause):
        return Period.MONTH
    if re.search(_PER_YEAR, clause):
        return Period.YEAR
    return None


def _field(clause: str) -> str | None:
    if kept := _kept_pot(clause):
        return f"goal_keep_{kept}"
    if _is_goal_clause(clause):
        return "goal_target_amount"
    for name, pattern in _FIELDS:
        if re.search(pattern, clause):
            if name == "debt":
                pays = re.search(r"\b(pay|paying|repay\w*)\b", clause) or _period(clause)
                return "monthly_debt_payment" if pays else "debt_balance"
            return name
    return None


def _amounts(text: str, asked: str | None) -> list[Amount]:
    found: dict[str, Amount] = {}
    unplaced: list[tuple[float, Period | None]] = []
    for sentence in re.split(r"(?<!\d)[.!?;\n]+|[.!?;](?=\s|$)", text):
        previous: str | None = None
        for clause in _clauses(sentence):
            values = [_value(m) for m in _AMOUNT.finditer(clause)]
            if not values:
                continue
            field = _field(clause)
            # "rent 900 and 700 for everything else": a clause without its own subject adds
            # to the monthly amount before it.
            if field is None and previous in FLOW_FIELDS:
                field = previous
            # "a loan of 4,000 and pay 200 a month on it": the payment on that debt.
            elif field is None and previous == "debt_balance":
                pays = re.search(r"\b(pay|paying|repay\w*)\b", clause) or _period(clause)
                field = "monthly_debt_payment" if pays else None
            if field is None:
                unplaced += [(v, _period(clause)) for v in values]
                continue
            period = _period(clause)
            if field in found:
                existing = found[field]
                existing.parts += values
                existing.period = existing.period or period
            else:
                found[field] = Amount(field=field, parts=values, period=period)  # type: ignore[arg-type]
            previous = field
    # A bare "300" answers the question that was asked.
    if asked and asked not in found and len(unplaced) == 1:
        value, period = unplaced[0]
        found[asked] = Amount(field=asked, parts=[value], period=period)  # type: ignore[arg-type]
    return list(found.values())


def _value(match: re.Match[str]) -> float:
    raw = match["num"]
    if re.fullmatch(r"\d{1,3}(?:[,.]\d{3})+", raw):
        number = float(re.sub(r"[,.]", "", raw))  # "2,400" and "8.000" are thousands
    else:
        number = float(raw)
    unit = match["unit"]
    if unit in ("k", "thousand"):
        number *= 1000
    elif unit in ("m", "million"):
        number *= 1_000_000
    return number
