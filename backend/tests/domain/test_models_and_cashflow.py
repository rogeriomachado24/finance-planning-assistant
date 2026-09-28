from datetime import date

import pytest

from app.domain.cashflow import (
    calculate_monthly_surplus,
    calculate_net_worth,
    calculate_savings_rate,
    summarize_position,
)
from app.domain.errors import InvalidInputError
from app.domain.models import Assumptions, FinancialProfile, Goal


class TestValidation:
    @pytest.mark.parametrize(
        "field",
        [
            "monthly_net_income",
            "monthly_expenses",
            "cash",
            "investments",
            "monthly_investment_contribution",
            "other_monthly_income",
            "debt_balance",
            "monthly_debt_payment",
        ],
    )
    def test_profile_rejects_negative_amounts(self, field):
        values = {"monthly_net_income": 2000, "monthly_expenses": 1500, field: -1}
        with pytest.raises(InvalidInputError, match=field):
            FinancialProfile(**values)

    @pytest.mark.parametrize("age", [-1, 121])
    def test_profile_rejects_implausible_age(self, age):
        with pytest.raises(InvalidInputError):
            FinancialProfile(monthly_net_income=2000, monthly_expenses=1500, age=age)

    def test_assumptions_reject_percent_entered_as_whole_number(self):
        with pytest.raises(InvalidInputError, match="annual_return"):
            Assumptions(annual_return=7)

    def test_assumptions_allow_negative_return(self):
        assert Assumptions(annual_return=-0.1).annual_return == -0.1

    @pytest.mark.parametrize("amount", [0, -100])
    def test_goal_requires_positive_target(self, amount):
        with pytest.raises(InvalidInputError):
            Goal(name="House", target_amount=amount, target_date=date(2030, 1, 1))

    def test_goal_requires_name(self):
        with pytest.raises(InvalidInputError):
            Goal(name="  ", target_amount=1000, target_date=date(2030, 1, 1))


class TestCashflow:
    def test_monthly_surplus(self):
        assert calculate_monthly_surplus(2500, 1700, 200, 300) == 700

    def test_monthly_surplus_can_be_negative(self):
        assert calculate_monthly_surplus(1500, 1800) == -300

    def test_monthly_surplus_rejects_negative_inputs(self):
        with pytest.raises(InvalidInputError):
            calculate_monthly_surplus(-1, 100)

    def test_savings_rate(self):
        assert calculate_savings_rate(700, 2800) == 0.25

    def test_savings_rate_is_undefined_without_income(self):
        assert calculate_savings_rate(-100, 0) is None

    def test_net_worth(self):
        assert calculate_net_worth(cash=5000, investments=20_000, debt=8000) == 17_000

    def test_summarize_position(self):
        profile = FinancialProfile(
            monthly_net_income=2500,
            other_monthly_income=300,
            monthly_expenses=1700,
            monthly_debt_payment=400,
            debt_balance=6000,
            cash=4000,
            investments=10_000,
        )
        position = summarize_position(profile)
        assert position.total_monthly_income == 2800
        assert position.monthly_surplus == 700
        assert position.savings_rate == 0.25
        assert position.liquid_assets == 14_000
        assert position.net_worth == 8000

    def test_summarize_position_caps_debt_payment_at_remaining_balance(self):
        profile = FinancialProfile(
            monthly_net_income=2000,
            monthly_expenses=1500,
            debt_balance=100,
            monthly_debt_payment=300,
        )
        assert summarize_position(profile).monthly_surplus == 400
