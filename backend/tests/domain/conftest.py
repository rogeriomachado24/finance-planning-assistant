from datetime import date

import pytest

from app.domain.models import Assumptions, FinancialProfile, Goal, GoalType

START = date(2026, 10, 1)


@pytest.fixture
def start() -> date:
    return START


@pytest.fixture
def profile() -> FinancialProfile:
    """A typical profile: 2,500 net income, 1,700 expenses, 400 invested monthly."""
    return FinancialProfile(
        monthly_net_income=2500,
        monthly_expenses=1700,
        cash=10_000,
        investments=15_000,
        monthly_investment_contribution=400,
        age=32,
    )


@pytest.fixture
def assumptions() -> Assumptions:
    return Assumptions(annual_return=0.05, annual_inflation=0.02)


@pytest.fixture
def goal() -> Goal:
    return Goal(
        name="Buy a house",
        target_amount=80_000,
        target_date=date(2032, 6, 1),
        goal_type=GoalType.HOUSE,
    )
