import math
from datetime import date

import pytest

from app.domain.errors import InvalidInputError
from app.domain.goals import (
    calculate_goal_date,
    calculate_goal_progress,
    calculate_required_monthly_contribution,
)
from app.domain.models import Assumptions, FinancialProfile
from app.domain.projection import project
from app.domain.rates import annual_to_monthly_rate


class TestGoalProgress:
    def test_partial_progress(self):
        progress = calculate_goal_progress(20_000, 80_000)
        assert progress.fraction == 0.25
        assert progress.remaining == 60_000
        assert not progress.reached

    def test_progress_is_capped_when_goal_is_exceeded(self):
        progress = calculate_goal_progress(90_000, 80_000)
        assert progress.fraction == 1.0
        assert progress.remaining == 0
        assert progress.reached

    def test_rejects_non_positive_target(self):
        with pytest.raises(InvalidInputError):
            calculate_goal_progress(1000, 0)


class TestGoalDate:
    def test_goal_already_reached_returns_start(self, start):
        profile = FinancialProfile(
            monthly_net_income=0, monthly_expenses=0, cash=50_000, investments=40_000
        )
        assert calculate_goal_date(profile, Assumptions(), 80_000, start) == start

    def test_zero_return_goal_date_follows_from_the_surplus(self, start):
        profile = FinancialProfile(monthly_net_income=2500, monthly_expenses=1700)
        # 800 per month, 8,000 target -> reached at the end of month 10
        assert calculate_goal_date(profile, Assumptions(), 8000, start) == date(2027, 8, 1)

    def test_positive_return_reaches_goal_sooner(self, start):
        profile = FinancialProfile(
            monthly_net_income=2500,
            monthly_expenses=1700,
            investments=30_000,
            monthly_investment_contribution=800,
        )
        flat = calculate_goal_date(profile, Assumptions(), 80_000, start)
        growing = calculate_goal_date(profile, Assumptions(annual_return=0.07), 80_000, start)
        assert growing < flat

    def test_unreachable_without_surplus_or_return(self, start):
        profile = FinancialProfile(monthly_net_income=2000, monthly_expenses=2000, cash=5000)
        assert calculate_goal_date(profile, Assumptions(), 80_000, start) is None

    def test_unreachable_when_expenses_outgrow_income(self, start):
        profile = FinancialProfile(monthly_net_income=2000, monthly_expenses=1900)
        assumptions = Assumptions(annual_expense_growth=0.05)
        assert calculate_goal_date(profile, assumptions, 80_000, start) is None

    def test_unreachable_within_a_short_horizon(self, start):
        profile = FinancialProfile(monthly_net_income=2500, monthly_expenses=1700)
        assert calculate_goal_date(profile, Assumptions(), 8000, start, max_months=9) is None


class TestRequiredMonthlyContribution:
    def test_zero_return_divides_the_gap_evenly(self):
        required = calculate_required_monthly_contribution(
            80_000, 68, current_cash=10_000, current_investments=15_000, annual_return=0
        )
        assert required == pytest.approx(55_000 / 68)

    def test_matches_closed_form_with_return(self):
        r = annual_to_monthly_rate(0.05)
        growth = (1 + r) ** 60
        expected = (80_000 - 5000 - 20_000 * growth) / ((growth - 1) / r)
        required = calculate_required_monthly_contribution(80_000, 60, 5000, 20_000, 0.05)
        assert required == pytest.approx(expected)

    def test_is_numerically_stable_for_near_zero_return(self):
        # Regression: (G - 1) / r loses precision for tiny r; found by Hypothesis.
        r = annual_to_monthly_rate(1e-9)
        annuity = math.fsum((1 + r) ** k for k in range(68))
        expected = (80_000 - 10_000 - 15_000 * (1 + r) ** 68) / annuity
        required = calculate_required_monthly_contribution(80_000, 68, 10_000, 15_000, 1e-9)
        assert required == pytest.approx(expected, rel=1e-12)

    def test_is_zero_when_goal_already_reached(self):
        assert calculate_required_monthly_contribution(80_000, 60, 50_000, 40_000, 0.05) == 0

    def test_is_zero_when_investment_growth_alone_covers_the_goal(self):
        # 70,000 at 5% for 10 years grows to about 114,000
        assert calculate_required_monthly_contribution(80_000, 120, 0, 70_000, 0.05) == 0

    def test_no_time_left_and_goal_not_reached_is_impossible(self):
        assert calculate_required_monthly_contribution(80_000, 0, 1000, 0, 0.05) is None

    def test_no_time_left_but_goal_reached_needs_nothing(self):
        assert calculate_required_monthly_contribution(80_000, 0, 80_000, 0, 0.05) == 0

    def test_higher_return_requires_less(self):
        low = calculate_required_monthly_contribution(80_000, 72, 0, 10_000, 0.02)
        high = calculate_required_monthly_contribution(80_000, 72, 0, 10_000, 0.08)
        assert high < low

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"target_amount": 0},
            {"months": -1},
            {"current_cash": -1},
            {"annual_return": 5},
        ],
    )
    def test_rejects_invalid_inputs(self, kwargs):
        args = {
            "target_amount": 80_000,
            "months": 60,
            "current_cash": 0,
            "current_investments": 0,
            "annual_return": 0.05,
        } | kwargs
        with pytest.raises(InvalidInputError):
            calculate_required_monthly_contribution(**args)

    def test_investing_the_required_amount_reaches_the_target_exactly(self, start):
        required = calculate_required_monthly_contribution(80_000, 68, 10_000, 15_000, 0.05)
        profile = FinancialProfile(
            monthly_net_income=required,
            monthly_expenses=0,
            cash=10_000,
            investments=15_000,
            monthly_investment_contribution=required,
        )
        final = project(profile, Assumptions(annual_return=0.05), start, 68).at(68)
        assert final.liquid_assets == pytest.approx(80_000)
