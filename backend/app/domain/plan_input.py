"""Arithmetic on figures a person described in words (Phase 3, "describe your plan").

The extractor (rules or a language model) only copies numbers from the description; any
calculation on them happens here, so it is tested like the rest of the engine and shown to
the user: "€900 + €700", "€36,000 a year ÷ 12", "20% of €300,000".
"""

from collections.abc import Sequence
from datetime import date
from enum import StrEnum

from app.domain.errors import InvalidInputError
from app.domain.periods import add_months, first_of_month


class Period(StrEnum):
    MONTH = "month"
    YEAR = "year"


def total(parts: Sequence[float]) -> float:
    """Adds the parts: "rent 900 and 700 for everything else" -> 1600."""
    if not parts:
        raise InvalidInputError("at least one amount is needed")
    if any(p < 0 for p in parts):
        raise InvalidInputError(f"amounts must be >= 0; got {list(parts)}")
    return float(sum(parts))


def per_month(amount: float, period: Period) -> float:
    """A yearly amount spread evenly over 12 months; a monthly amount unchanged."""
    if amount < 0:
        raise InvalidInputError(f"amount must be >= 0; got {amount}")
    return amount / 12 if period is Period.YEAR else amount


def share_of(percent: float, amount: float) -> float:
    """A percentage of a price: "a 20% deposit on a 300k house" -> 60000."""
    if not 0 < percent <= 100:
        raise InvalidInputError(f"percent must be above 0 and at most 100; got {percent}")
    if amount <= 0:
        raise InvalidInputError(f"amount must be > 0; got {amount}")
    return amount * percent / 100


def months_from_now(today: date, months: int) -> date:
    """A date some months ahead: "in 6 years" from any day in October 2026 -> 1 Oct 2032
    (projections start on the first of the current month)."""
    if months <= 0:
        raise InvalidInputError(f"months must be > 0; got {months}")
    return add_months(first_of_month(today), months)
