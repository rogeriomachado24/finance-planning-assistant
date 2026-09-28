"""Goal progress, goal date and required contribution."""

from dataclasses import dataclass
from datetime import date

from app.domain.errors import InvalidInputError
from app.domain.models import Assumptions, FinancialProfile
from app.domain.projection import MAX_PROJECTION_MONTHS, Projection, project
from app.domain.rates import annual_to_monthly_rate, compound_growth_minus_one


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
    """First month whose closing liquid assets reach the target, or None within the horizon."""
    for snapshot in projection.snapshots:
        if snapshot.liquid_assets >= target_amount:
            return snapshot.month
    return None


def calculate_goal_date(
    profile: FinancialProfile,
    assumptions: Assumptions,
    target_amount: float,
    start: date,
    max_months: int = MAX_PROJECTION_MONTHS,
) -> date | None:
    """Date on which liquid assets first reach the target under the current plan.

    Returns `start` when the goal is already reached, and None when it is not reached
    within `max_months` (50 years by default).
    """
    if target_amount <= 0:
        raise InvalidInputError(f"target_amount must be > 0; got {target_amount}")
    projection = project(profile, assumptions, start, max_months)
    month = find_goal_month(projection, target_amount)
    return None if month is None else projection.at(month).date


def calculate_required_monthly_contribution(
    target_amount: float,
    months: int,
    current_cash: float,
    current_investments: float,
    annual_return: float,
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
    """
    if target_amount <= 0:
        raise InvalidInputError(f"target_amount must be > 0; got {target_amount}")
    if months < 0:
        raise InvalidInputError(f"months must be >= 0; got {months}")
    if current_cash < 0 or current_investments < 0:
        raise InvalidInputError("current_cash and current_investments must be >= 0")

    monthly_return = annual_to_monthly_rate(annual_return)
    growth_minus_one = compound_growth_minus_one(monthly_return, months)
    gap = target_amount - current_cash - current_investments * (1 + growth_minus_one)
    if gap <= 0:
        return 0.0
    if months == 0:
        return None

    annuity_factor = months if monthly_return == 0 else growth_minus_one / monthly_return
    return gap / annuity_factor
