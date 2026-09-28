"""The sample person used across service and API tests."""

from datetime import date

from app.domain.models import Assumptions, FinancialProfile, Goal, GoalType

TODAY = date(2026, 10, 15)
"""Mid-month on purpose: projections must start on 1 Oct 2026."""

PROFILE = FinancialProfile(
    monthly_net_income=2500,
    monthly_expenses=1700,
    cash=10_000,
    investments=15_000,
    monthly_investment_contribution=400,
    age=32,
)
BASE = Assumptions(
    annual_return=0.05, annual_salary_growth=0.02, annual_expense_growth=0.02, annual_inflation=0.02
)
GOAL = Goal(
    name="Buy a house",
    target_amount=80_000,
    target_date=date(2032, 6, 1),
    goal_type=GoalType.HOUSE,
)
