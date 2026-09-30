from datetime import date

import pytest

from app.domain.errors import InvalidInputError
from app.domain.models import Assumptions, FinancialProfile
from app.domain.projection import (
    MAX_PROJECTION_MONTHS,
    WarningCode,
    project,
    project_cash_balance,
    project_investment_balance,
    project_total_assets,
)
from app.domain.rates import annual_to_monthly_rate


def fv_lump_sum(amount: float, monthly_rate: float, months: int) -> float:
    return amount * (1 + monthly_rate) ** months


def fv_annuity(payment: float, monthly_rate: float, months: int) -> float:
    """Future value of `payment` at the end of each month (ordinary annuity)."""
    if monthly_rate == 0:
        return payment * months
    return payment * ((1 + monthly_rate) ** months - 1) / monthly_rate


def warning_months(projection) -> dict[WarningCode, int]:
    return {w.code: w.month for w in projection.warnings}


class TestStructure:
    def test_returns_opening_snapshot_plus_one_per_month(self, profile, assumptions, start):
        projection = project(profile, assumptions, start, 24)
        assert projection.months == 24
        opening = projection.at(0)
        assert opening.date == start
        assert opening.cash == profile.cash
        assert opening.investments == profile.investments
        assert opening.surplus == 0

    def test_month_dates_advance_by_calendar_month(self, profile, assumptions, start):
        projection = project(profile, assumptions, start, 3)
        assert [s.date for s in projection.snapshots] == [
            date(2026, 10, 1),
            date(2026, 11, 1),
            date(2026, 12, 1),
            date(2027, 1, 1),
        ]

    @pytest.mark.parametrize("months", [-1, MAX_PROJECTION_MONTHS + 1])
    def test_rejects_out_of_range_horizon(self, profile, assumptions, start, months):
        with pytest.raises(InvalidInputError):
            project(profile, assumptions, start, months)

    def test_series_helpers_match_the_projection(self, profile, assumptions, start):
        projection = project(profile, assumptions, start, 36)
        assert project_cash_balance(profile, assumptions, start, 36) == [
            s.cash for s in projection.snapshots
        ]
        assert project_investment_balance(profile, assumptions, start, 36) == [
            s.investments for s in projection.snapshots
        ]
        totals = project_total_assets(profile, assumptions, start, 36)
        assert totals == [s.cash + s.investments for s in projection.snapshots]


class TestGrowthAndContributions:
    def test_zero_return_without_contribution_accumulates_surplus_as_cash(self, start):
        profile = FinancialProfile(
            monthly_net_income=2500, monthly_expenses=1700, cash=10_000, investments=15_000
        )
        final = project(profile, Assumptions(), start, 12).at(12)
        assert final.cash == pytest.approx(10_000 + 800 * 12)
        assert final.investments == 15_000

    def test_compound_growth_of_existing_investments(self, start):
        profile = FinancialProfile(monthly_net_income=0, monthly_expenses=0, investments=10_000)
        final = project(profile, Assumptions(annual_return=0.06), start, 24).at(24)
        assert final.investments == pytest.approx(10_000 * 1.06**2)

    def test_monthly_contributions_match_annuity_formula(self, start):
        profile = FinancialProfile(
            monthly_net_income=1000, monthly_expenses=0, monthly_investment_contribution=1000
        )
        monthly_rate = annual_to_monthly_rate(0.05)
        final = project(profile, Assumptions(annual_return=0.05), start, 120).at(120)
        assert final.investments == pytest.approx(fv_annuity(1000, monthly_rate, 120))
        assert final.cash == pytest.approx(0)

    def test_starting_balance_and_contributions_combine(self, start):
        profile = FinancialProfile(
            monthly_net_income=500,
            monthly_expenses=0,
            investments=20_000,
            monthly_investment_contribution=500,
        )
        r = annual_to_monthly_rate(0.07)
        final = project(profile, Assumptions(annual_return=0.07), start, 60).at(60)
        expected = fv_lump_sum(20_000, r, 60) + fv_annuity(500, r, 60)
        assert final.investments == pytest.approx(expected)

    def test_contribution_starts_earning_the_following_month(self, start):
        profile = FinancialProfile(
            monthly_net_income=100, monthly_expenses=0, monthly_investment_contribution=100
        )
        projection = project(profile, Assumptions(annual_return=0.12), start, 2)
        r = annual_to_monthly_rate(0.12)
        assert projection.at(1).investments == pytest.approx(100)
        assert projection.at(2).investments == pytest.approx(100 * (1 + r) + 100)

    def test_leftover_surplus_goes_to_cash(self, profile, start):
        final = project(profile, Assumptions(), start, 10).at(10)
        # surplus 800, of which 400 is invested
        assert final.cash == pytest.approx(profile.cash + 400 * 10)
        assert final.investments == pytest.approx(profile.investments + 400 * 10)

    def test_negative_return_shrinks_investments(self, start):
        profile = FinancialProfile(monthly_net_income=0, monthly_expenses=0, investments=10_000)
        final = project(profile, Assumptions(annual_return=-0.1), start, 12).at(12)
        assert final.investments == pytest.approx(9000)


class TestIncomeAndExpenseGrowth:
    def test_salary_growth_is_applied_in_annual_steps(self, start):
        profile = FinancialProfile(monthly_net_income=2000, monthly_expenses=0)
        projection = project(profile, Assumptions(annual_salary_growth=0.10), start, 25)
        assert projection.at(1).income == 2000
        assert projection.at(12).income == 2000
        assert projection.at(13).income == pytest.approx(2200)
        assert projection.at(25).income == pytest.approx(2420)

    def test_other_income_does_not_grow(self, start):
        profile = FinancialProfile(
            monthly_net_income=2000, other_monthly_income=500, monthly_expenses=0
        )
        projection = project(profile, Assumptions(annual_salary_growth=0.10), start, 13)
        assert projection.at(13).income == pytest.approx(2200 + 500)

    def test_expense_growth_is_applied_in_annual_steps(self, start):
        profile = FinancialProfile(monthly_net_income=3000, monthly_expenses=1000)
        projection = project(profile, Assumptions(annual_expense_growth=0.03), start, 13)
        assert projection.at(12).expenses == 1000
        assert projection.at(13).expenses == pytest.approx(1030)
        assert projection.at(13).surplus == pytest.approx(3000 - 1030)

    def test_salary_growth_increases_accumulated_cash(self, profile, start):
        flat = project(profile, Assumptions(), start, 60).at(60)
        growing = project(profile, Assumptions(annual_salary_growth=0.05), start, 60).at(60)
        assert growing.cash > flat.cash

    def test_expense_growth_reduces_accumulated_cash(self, profile, start):
        flat = project(profile, Assumptions(), start, 60).at(60)
        growing = project(profile, Assumptions(annual_expense_growth=0.05), start, 60).at(60)
        assert growing.cash < flat.cash


class TestDebt:
    def test_payment_stops_when_debt_is_repaid(self, start):
        profile = FinancialProfile(
            monthly_net_income=2000,
            monthly_expenses=1000,
            debt_balance=1000,
            monthly_debt_payment=300,
        )
        projection = project(profile, Assumptions(), start, 5)
        assert [s.debt_payment for s in projection.snapshots[1:]] == [300, 300, 300, 100, 0]
        assert [s.debt for s in projection.snapshots[1:]] == [700, 400, 100, 0, 0]
        assert projection.at(5).surplus == 1000
        assert warning_months(projection)[WarningCode.DEBT_PAID_OFF] == 4

    def test_net_worth_subtracts_debt(self, start):
        profile = FinancialProfile(
            monthly_net_income=0, monthly_expenses=0, cash=5000, debt_balance=2000
        )
        opening = project(profile, Assumptions(), start, 0).at(0)
        assert opening.liquid_assets == 5000
        assert opening.net_worth == 3000


class TestShortfalls:
    def test_contribution_is_limited_to_available_cash(self, start):
        profile = FinancialProfile(
            monthly_net_income=1000,
            monthly_expenses=800,
            cash=1000,
            monthly_investment_contribution=500,
        )
        projection = project(profile, Assumptions(), start, 5)
        contributions = [s.contribution for s in projection.snapshots[1:]]
        assert contributions == [500, 500, 500, 300, 200]
        assert all(s.cash >= 0 for s in projection.snapshots)
        assert warning_months(projection)[WarningCode.CONTRIBUTION_REDUCED] == 4

    def test_negative_surplus_draws_cash_then_investments_then_deficit(self, start):
        profile = FinancialProfile(
            monthly_net_income=1000, monthly_expenses=1500, cash=1000, investments=1000
        )
        projection = project(profile, Assumptions(), start, 5)
        assert [s.cash for s in projection.snapshots[1:]] == [500, 0, 0, 0, -500]
        assert [s.investments for s in projection.snapshots[1:]] == [1000, 1000, 500, 0, 0]
        assert [s.withdrawal for s in projection.snapshots[1:]] == [0, 0, 500, 500, 0]
        months = warning_months(projection)
        assert months[WarningCode.INVESTMENTS_WITHDRAWN] == 3
        assert months[WarningCode.LIQUID_FUNDS_EXHAUSTED] == 5

    def test_healthy_plan_has_no_warnings(self, profile, assumptions, start):
        assert project(profile, assumptions, start, 120).warnings == ()


class TestYearlyReturns:
    """A sequence of yearly returns (Phase 2: market drop and Monte Carlo)."""

    def test_each_year_uses_its_own_return(self, start):
        profile = FinancialProfile(monthly_net_income=0, monthly_expenses=0, investments=10_000)
        projection = project(profile, Assumptions(), start, 24, [-0.30, 0.10])
        assert projection.at(12).investments == pytest.approx(7_000)
        assert projection.at(24).investments == pytest.approx(7_700)

    def test_constant_sequence_matches_the_assumed_return(self, profile, assumptions, start):
        assert project(profile, assumptions, start, 60, [0.05] * 5) == project(
            profile, assumptions, start, 60
        )

    def test_a_year_above_100_percent_is_allowed(self, start):
        profile = FinancialProfile(monthly_net_income=0, monthly_expenses=0, investments=1_000)
        final = project(profile, Assumptions(), start, 12, [1.5]).at(12)
        assert final.investments == pytest.approx(2_500)

    def test_rejects_too_few_returns(self, profile, assumptions, start):
        with pytest.raises(InvalidInputError):
            project(profile, assumptions, start, 25, [0.05, 0.05])

    def test_rejects_a_loss_of_everything(self, profile, assumptions, start):
        with pytest.raises(InvalidInputError):
            project(profile, assumptions, start, 12, [-1.0])
