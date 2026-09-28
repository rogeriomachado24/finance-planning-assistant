"""Point-in-time cash-flow figures for the dashboard."""

from dataclasses import dataclass

from app.domain.errors import InvalidInputError
from app.domain.models import FinancialProfile


def calculate_monthly_surplus(
    monthly_net_income: float,
    monthly_expenses: float,
    other_monthly_income: float = 0.0,
    monthly_debt_payment: float = 0.0,
) -> float:
    """surplus = net income + other income - expenses - debt payment.

    Can be negative: the user spends more than they earn.
    """
    for name, value in {
        "monthly_net_income": monthly_net_income,
        "monthly_expenses": monthly_expenses,
        "other_monthly_income": other_monthly_income,
        "monthly_debt_payment": monthly_debt_payment,
    }.items():
        if value < 0:
            raise InvalidInputError(f"{name} must be >= 0; got {value}")
    return monthly_net_income + other_monthly_income - monthly_expenses - monthly_debt_payment


def calculate_savings_rate(monthly_surplus: float, total_monthly_income: float) -> float | None:
    """savings rate = surplus / total income. None when there is no income (undefined)."""
    if total_monthly_income < 0:
        raise InvalidInputError(f"total_monthly_income must be >= 0; got {total_monthly_income}")
    if total_monthly_income == 0:
        return None
    return monthly_surplus / total_monthly_income


def calculate_net_worth(cash: float, investments: float, debt: float) -> float:
    """net worth = cash + investments - debt."""
    return cash + investments - debt


@dataclass(frozen=True)
class FinancialPosition:
    total_monthly_income: float
    monthly_expenses: float
    monthly_debt_payment: float
    monthly_surplus: float
    savings_rate: float | None
    liquid_assets: float
    net_worth: float


def summarize_position(profile: FinancialProfile) -> FinancialPosition:
    """Today's position, as shown on the dashboard."""
    debt_payment = min(profile.monthly_debt_payment, profile.debt_balance)
    surplus = calculate_monthly_surplus(
        profile.monthly_net_income,
        profile.monthly_expenses,
        profile.other_monthly_income,
        debt_payment,
    )
    return FinancialPosition(
        total_monthly_income=profile.total_monthly_income,
        monthly_expenses=profile.monthly_expenses,
        monthly_debt_payment=debt_payment,
        monthly_surplus=surplus,
        savings_rate=calculate_savings_rate(surplus, profile.total_monthly_income),
        liquid_assets=profile.liquid_assets,
        net_worth=calculate_net_worth(profile.cash, profile.investments, profile.debt_balance),
    )
