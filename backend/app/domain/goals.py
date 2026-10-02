"""Goal progress, goal date and required contribution."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from app.domain.errors import InvalidInputError
from app.domain.models import NOTHING_KEPT, Assumptions, FinancialProfile, KeptAside
from app.domain.periods import months_between
from app.domain.projection import MAX_PROJECTION_MONTHS, Projection, project
from app.domain.rates import (
    annual_to_monthly_rate,
    compound_growth_minus_one,
    yearly_to_monthly_rate,
)


def months_to_target_date(
    target_date: date, start: date, max_months: int = MAX_PROJECTION_MONTHS
) -> int:
    """Whole months from the projection start to the goal's target date.

    Raises when the date is before the start (the goal can't be projected) or beyond the
    projection horizon (50 years by default).
    """
    # Compare the dates themselves: months_between counts whole months, so a date a few
    # days before the start would still come out as 0 rather than negative.
    if target_date < start:
        raise InvalidInputError(
            f"goal target date {target_date} is before the projection start {start}"
        )
    months = months_between(start, target_date)
    if months > max_months:
        raise InvalidInputError(
            f"goal target date is more than {max_months} months after the projection start"
        )
    return months


@dataclass(frozen=True)
class GoalProgress:
    current_amount: float
    target_amount: float
    remaining: float
    fraction: float
    """Share of the target already accumulated, capped at 1.0."""

    @property
    def reached(self) -> bool:
        return self.remaining == 0


def calculate_goal_progress(current_amount: float, target_amount: float) -> GoalProgress:
    """progress = min(current / target, 1); remaining = max(target - current, 0)."""
    if target_amount <= 0:
        raise InvalidInputError(f"target_amount must be > 0; got {target_amount}")
    return GoalProgress(
        current_amount=current_amount,
        target_amount=target_amount,
        remaining=max(target_amount - current_amount, 0.0),
        fraction=min(max(current_amount / target_amount, 0.0), 1.0),
    )


def find_goal_month(projection: Projection, target_amount: float) -> int | None:
    """First month whose counted amount (cash + investments minus what the goal keeps aside)
    reaches the target, or None within the horizon."""
    for snapshot in projection.snapshots:
        if snapshot.counted >= target_amount:
            return snapshot.month
    return None


def calculate_goal_date(
    profile: FinancialProfile,
    assumptions: Assumptions,
    target_amount: float,
    start: date,
    max_months: int = MAX_PROJECTION_MONTHS,
    kept_aside: KeptAside = NOTHING_KEPT,
) -> date | None:
    """Date on which the counted amount first reaches the target under the current plan.

    Returns `start` when the goal is already reached, and None when it is not reached
    within `max_months` (50 years by default).
    """
    if target_amount <= 0:
        raise InvalidInputError(f"target_amount must be > 0; got {target_amount}")
    projection = project(profile, assumptions, start, max_months, kept_aside=kept_aside)
    month = find_goal_month(projection, target_amount)
    return None if month is None else projection.at(month).date


def calculate_required_monthly_contribution(
    target_amount: float,
    months: int,
    current_cash: float,
    current_investments: float,
    annual_return: float,
    annual_returns: Sequence[float] | None = None,
    kept_aside: KeptAside = NOTHING_KEPT,
) -> float | None:
    """Monthly amount that, invested at the assumed return from next month, brings today's
    cash + investments to the target after `months` months.

        G = (1 + r_m)^n                         growth factor over n months
        A = (G - 1) / r_m   (A = n if r_m = 0)  future value of 1 EUR invested each month-end
        required = max(0, (target - cash - investments * G) / A)

    Cash earns nothing; existing investments keep compounding. Independent of income:
    compare the result with the monthly surplus to judge affordability.
    G - 1 is computed with expm1/log1p so near-zero returns don't lose precision.

    Returns 0 when the goal is already covered, and None when `months` is 0 and the goal
    is not yet reached (no time left to contribute).

    With `annual_returns` (one return per projected year, e.g. a market drop in year 1),
    G and A are built month by month instead: a contribution made at the end of month k
    grows over months k+1..n, so A is the sum of those growth products.

    With `kept_aside`, only what the goal may use counts: cash above the kept savings, and
    the investments beyond the kept slice, whose growth isn't counted either:
        required = max(0, (target - max(0, cash - kept_savings)
                           - (investments - kept_investments) * G) / A)
    """
    if target_amount <= 0:
        raise InvalidInputError(f"target_amount must be > 0; got {target_amount}")
    if months < 0:
        raise InvalidInputError(f"months must be >= 0; got {months}")
    if current_cash < 0 or current_investments < 0:
        raise InvalidInputError("current_cash and current_investments must be >= 0")
    # What the goal may use: cash above the kept savings (cash doesn't grow), and the
    # investments minus the kept slice (negative if more is kept than held: new
    # contributions first make up the slice, as in the projection).
    usable_cash = max(0.0, current_cash - kept_aside.savings)
    usable_investments = current_investments - kept_aside.investments

    if annual_returns is not None:
        return _required_with_yearly_returns(
            target_amount, months, usable_cash, usable_investments, annual_returns
        )

    monthly_return = annual_to_monthly_rate(annual_return)
    growth_minus_one = compound_growth_minus_one(monthly_return, months)
    gap = target_amount - usable_cash - usable_investments * (1 + growth_minus_one)
    if gap <= 0:
        return 0.0
    if months == 0:
        return None

    annuity_factor = months if monthly_return == 0 else growth_minus_one / monthly_return
    return gap / annuity_factor


def _required_with_yearly_returns(
    target_amount: float,
    months: int,
    current_cash: float,
    current_investments: float,
    annual_returns: Sequence[float],
) -> float | None:
    rates = [yearly_to_monthly_rate(annual_returns[k // 12]) for k in range(months)]
    growth_after = 1.0  # growth from the end of month k to the end of month n
    annuity_factor = 0.0
    for rate in reversed(rates):  # month n down to month 1
        annuity_factor += growth_after
        growth_after *= 1 + rate
    gap = target_amount - current_cash - current_investments * growth_after
    if gap <= 0:
        return 0.0
    if months == 0:
        return None
    return gap / annuity_factor
