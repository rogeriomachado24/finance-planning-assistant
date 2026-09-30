"""Month-by-month projection engine.

Each month k = 1..N, with y = (k - 1) // 12 completed years:

    income_k       = net_income * (1 + salary_growth)^y + other_income
    expenses_k     = expenses * (1 + expense_growth)^y
    debt_payment_k = min(planned_debt_payment, debt_balance)
    surplus_k      = income_k - expenses_k - debt_payment_k

    investments   *= (1 + r_m)                    growth on the opening balance
    available      = cash + surplus_k
    contribution_k = min(planned_contribution, max(available, 0))
    cash           = available - contribution_k   leftover surplus stays in cash
    if cash < 0:   sell investments to cover the gap (withdrawal_k)
    investments   += contribution_k               end-of-month contribution

If cash is still negative after selling all investments, the plan has an unfunded deficit.
See docs/PHASE1_DESIGN.md section 3 for the full model and its simplifications.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from app.domain.errors import InvalidInputError
from app.domain.models import Assumptions, FinancialProfile
from app.domain.periods import month_dates
from app.domain.rates import annual_step_factor, yearly_to_monthly_rate

MAX_PROJECTION_MONTHS = 50 * 12

# Tolerance for float comparisons on euro amounts (well below one cent).
EPSILON = 1e-9


@dataclass(frozen=True)
class MonthSnapshot:
    """Balances at the end of `month` and the flows during it. Month 0 is the opening
    position, with all flows set to zero."""

    month: int
    date: date
    income: float
    expenses: float
    debt_payment: float
    surplus: float
    contribution: float
    withdrawal: float
    cash: float
    investments: float
    debt: float

    @property
    def liquid_assets(self) -> float:
        """Cash + investments: the amount that counts toward a goal."""
        return self.cash + self.investments

    @property
    def net_worth(self) -> float:
        return self.cash + self.investments - self.debt


class WarningCode(StrEnum):
    CONTRIBUTION_REDUCED = "contribution_reduced"
    INVESTMENTS_WITHDRAWN = "investments_withdrawn"
    LIQUID_FUNDS_EXHAUSTED = "liquid_funds_exhausted"
    DEBT_PAID_OFF = "debt_paid_off"


_WARNING_MESSAGES = {
    WarningCode.CONTRIBUTION_REDUCED: (
        "Available cash does not cover the planned investment contribution; "
        "only the available amount is invested."
    ),
    WarningCode.INVESTMENTS_WITHDRAWN: (
        "Monthly spending exceeds income and cash is exhausted; investments are sold to cover it."
    ),
    WarningCode.LIQUID_FUNDS_EXHAUSTED: (
        "Cash and investments are exhausted; the plan has an unfunded monthly deficit."
    ),
    WarningCode.DEBT_PAID_OFF: "Debt is fully repaid; the monthly payment becomes surplus.",
}


@dataclass(frozen=True)
class ProjectionWarning:
    code: WarningCode
    month: int
    """First month in which the condition occurs."""
    date: date

    @property
    def message(self) -> str:
        return _WARNING_MESSAGES[self.code]


@dataclass(frozen=True)
class Projection:
    snapshots: tuple[MonthSnapshot, ...]
    warnings: tuple[ProjectionWarning, ...]

    @property
    def months(self) -> int:
        return len(self.snapshots) - 1

    def at(self, month: int) -> MonthSnapshot:
        return self.snapshots[month]


def project(
    profile: FinancialProfile,
    assumptions: Assumptions,
    start: date,
    months: int,
    annual_returns: Sequence[float] | None = None,
) -> Projection:
    """Simulate `months` months from `start`. Returns months + 1 snapshots (0..months).

    `annual_returns` sets the investment return of each projected year (index 0 = months
    1-12). By default every year earns `assumptions.annual_return`; a market drop or a
    Monte Carlo future passes its own sequence.
    """
    if not 0 <= months <= MAX_PROJECTION_MONTHS:
        raise InvalidInputError(
            f"months must be between 0 and {MAX_PROJECTION_MONTHS}; got {months}"
        )

    years = max(1, -(-months // 12))  # years touched by the projection, rounded up
    if annual_returns is None:
        annual_returns = [assumptions.annual_return] * years
    elif len(annual_returns) < years:
        raise InvalidInputError(f"{years} yearly returns needed; got {len(annual_returns)}")
    monthly_returns = [yearly_to_monthly_rate(r) for r in annual_returns[:years]]
    # Salary and expenses change once a year, so their growth factors are per year too.
    salary_factors = [annual_step_factor(assumptions.annual_salary_growth, y) for y in range(years)]
    expense_factors = [
        annual_step_factor(assumptions.annual_expense_growth, y) for y in range(years)
    ]
    dates = month_dates(start, months)
    cash = profile.cash
    investments = profile.investments
    debt = profile.debt_balance

    snapshots = [
        MonthSnapshot(
            month=0,
            date=start,
            income=0.0,
            expenses=0.0,
            debt_payment=0.0,
            surplus=0.0,
            contribution=0.0,
            withdrawal=0.0,
            cash=cash,
            investments=investments,
            debt=debt,
        )
    ]
    warnings: dict[WarningCode, ProjectionWarning] = {}

    def warn(code: WarningCode, month: int) -> None:
        if code not in warnings:
            warnings[code] = ProjectionWarning(code, month, dates[month])

    for month in range(1, months + 1):
        completed_years = (month - 1) // 12
        monthly_return = monthly_returns[completed_years]
        income = (
            profile.monthly_net_income * salary_factors[completed_years]
            + profile.other_monthly_income
        )
        expenses = profile.monthly_expenses * expense_factors[completed_years]
        debt_payment = min(profile.monthly_debt_payment, debt)
        surplus = income - expenses - debt_payment
        debt_before = debt
        debt -= debt_payment

        investments *= 1 + monthly_return
        available = cash + surplus
        contribution = min(profile.monthly_investment_contribution, max(available, 0.0))
        cash = available - contribution

        withdrawal = 0.0
        if cash < 0:
            withdrawal = min(-cash, investments)
            investments -= withdrawal
            cash += withdrawal
        investments += contribution

        if contribution < profile.monthly_investment_contribution - EPSILON:
            warn(WarningCode.CONTRIBUTION_REDUCED, month)
        if withdrawal > EPSILON:
            warn(WarningCode.INVESTMENTS_WITHDRAWN, month)
        if cash < -EPSILON:
            warn(WarningCode.LIQUID_FUNDS_EXHAUSTED, month)
        if debt_before > 0 and debt <= EPSILON:
            warn(WarningCode.DEBT_PAID_OFF, month)

        snapshots.append(
            MonthSnapshot(
                month=month,
                date=dates[month],
                income=income,
                expenses=expenses,
                debt_payment=debt_payment,
                surplus=surplus,
                contribution=contribution,
                withdrawal=withdrawal,
                cash=cash,
                investments=investments,
                debt=debt,
            )
        )

    ordered = sorted(warnings.values(), key=lambda w: (w.month, w.code))
    return Projection(snapshots=tuple(snapshots), warnings=tuple(ordered))


def project_cash_balance(
    profile: FinancialProfile, assumptions: Assumptions, start: date, months: int
) -> list[float]:
    """Cash balance at the end of each month 0..months."""
    return [s.cash for s in project(profile, assumptions, start, months).snapshots]


def project_investment_balance(
    profile: FinancialProfile, assumptions: Assumptions, start: date, months: int
) -> list[float]:
    """Investment balance at the end of each month 0..months."""
    return [s.investments for s in project(profile, assumptions, start, months).snapshots]


def project_total_assets(
    profile: FinancialProfile, assumptions: Assumptions, start: date, months: int
) -> list[float]:
    """Liquid assets (cash + investments) at the end of each month 0..months."""
    return [s.liquid_assets for s in project(profile, assumptions, start, months).snapshots]
