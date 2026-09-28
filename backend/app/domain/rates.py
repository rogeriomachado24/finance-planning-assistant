"""Rate conversions and validation.

All rates are decimals: 0.07 means 7% per year.
"""

import math

from app.domain.errors import InvalidInputError

MIN_RATE_EXCLUSIVE = -1.0
MAX_RATE = 1.0


def validate_annual_rate(rate: float, name: str = "rate") -> float:
    """Reject rates of -100% or less (meaningless) and above 100% (almost certainly a typo,
    e.g. 7 entered instead of 0.07)."""
    if not MIN_RATE_EXCLUSIVE < rate <= MAX_RATE:
        raise InvalidInputError(
            f"{name} must be a decimal between -1 (exclusive) and 1, e.g. 0.05 for 5%; got {rate}"
        )
    return rate


def annual_to_monthly_rate(annual_rate: float) -> float:
    """Convert an annual rate to the equivalent monthly compounding rate.

        r_m = (1 + r_annual)^(1/12) - 1

    Twelve months at r_m compound to exactly r_annual. Dividing by 12 would overstate
    the annual result (7% / 12 compounded monthly gives about 7.23%).

    Computed as expm1(log1p(r) / 12) to stay precise for rates close to zero.
    """
    validate_annual_rate(annual_rate, "annual_rate")
    return math.expm1(math.log1p(annual_rate) / 12)


def compound_growth_minus_one(monthly_rate: float, months: int) -> float:
    """(1 + r)^n - 1, computed without cancellation error when r is close to zero."""
    return math.expm1(months * math.log1p(monthly_rate))


def annual_step_factor(annual_rate: float, completed_years: int) -> float:
    """Growth factor after `completed_years` annual steps: (1 + r)^years.

    Used for salary and expense growth, which change once a year rather than monthly.
    """
    if completed_years < 0:
        raise InvalidInputError(f"completed_years must be >= 0; got {completed_years}")
    return (1 + annual_rate) ** completed_years
