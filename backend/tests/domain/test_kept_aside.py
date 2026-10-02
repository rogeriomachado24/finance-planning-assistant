"""Money kept aside (docs/KEPT_ASIDE_DESIGN.md): an amount of savings and of today's
investments that a goal doesn't use. Nothing kept changes nothing."""

from dataclasses import replace
from datetime import date

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.domain.errors import InvalidInputError
from app.domain.goals import calculate_required_monthly_contribution
from app.domain.models import Assumptions, FinancialProfile, Goal, GoalType, KeptAside
from app.domain.projection import project
from app.domain.scenarios import Scenario, run_scenario
from app.domain.uncertainty import simulate_uncertainty

START = date(2026, 10, 1)
RETURN_5 = Assumptions(annual_return=0.05)
# The car example: €10,000 saved, €10,000 invested, nothing coming in or going out.
STILL = FinancialProfile(monthly_net_income=0, monthly_expenses=0, cash=10_000, investments=10_000)
CAR = Goal("Car", 20_000, date(2028, 10, 1), GoalType.VEHICLE)
KEEP = KeptAside(savings=5_000, investments=7_000)


class TestProjection:
    def test_nothing_kept_counts_everything(self):
        for s in project(STILL, RETURN_5, START, 24).snapshots:
            assert (s.kept_savings, s.kept_investments) == (0, 0)
            assert s.counted == s.liquid_assets

    def test_car_example_today(self):
        today = project(STILL, RETURN_5, START, 0, kept_aside=KEEP).at(0)
        assert (today.kept_savings, today.kept_investments) == (5_000, 7_000)
        assert today.counted == 8_000  # 5,000 of savings + 3,000 of investments

    def test_kept_investments_keep_their_own_growth(self):
        """€7,000 of €10,000 invested is kept aside: after a year at 5% the slice is €7,350,
        and only the other €3,150 counts."""
        year = project(STILL, RETURN_5, START, 12, kept_aside=KEEP).at(12)
        assert year.kept_investments == pytest.approx(7_350)
        assert year.kept_savings == 5_000  # cash earns nothing
        assert year.counted == pytest.approx(5_000 + 3_150)

    def test_a_pot_below_its_kept_amount_counts_nothing_and_keeps_what_is_there(self):
        short = replace(STILL, cash=3_000)
        today = project(short, RETURN_5, START, 0, kept_aside=KEEP).at(0)
        assert today.kept_savings == 3_000
        assert today.counted == 3_000  # only investments beyond the €7,000 slice

    def test_new_savings_count_fully(self):
        saving = replace(STILL, monthly_net_income=500)  # €500 a month into cash
        month = project(saving, Assumptions(), START, 1, kept_aside=KEEP).at(1)
        assert month.counted == 8_000 + 500

    @given(
        cash=st.floats(0, 50_000),
        investments=st.floats(0, 50_000),
        keep_savings=st.floats(0, 60_000),
        keep_investments=st.floats(0, 60_000),
        expenses=st.floats(0, 3_000),
    )
    def test_counted_plus_kept_is_always_cash_plus_investments(
        self, cash, investments, keep_savings, keep_investments, expenses
    ):
        profile = FinancialProfile(
            monthly_net_income=1_000, monthly_expenses=expenses, cash=cash, investments=investments
        )
        kept = KeptAside(keep_savings, keep_investments)
        for s in project(profile, RETURN_5, START, 24, kept_aside=kept).snapshots:
            assert s.counted + s.kept_aside == pytest.approx(s.liquid_assets)
            assert 0 <= s.kept_savings <= max(s.cash, 0) + 1e-9
            assert 0 <= s.kept_investments <= max(s.investments, 0) + 1e-9


class TestGoal:
    def test_car_example_progress_and_date(self):
        result = run_scenario(Scenario("Plan"), STILL, RETURN_5, replace(CAR, **_keep()), START)
        assert result.goal_progress.current_amount == 8_000
        assert result.goal_progress.remaining == 12_000
        assert not result.reaches_goal  # nothing comes in: €8,000 + growth isn't €20,000
        everything = run_scenario(Scenario("Plan"), STILL, RETURN_5, CAR, START)
        assert everything.months_to_goal == 0  # without keeping anything: already covered

    def test_needed_per_month_reaches_the_target_exactly(self):
        months = 24
        required = calculate_required_monthly_contribution(
            20_000, months, 10_000, 10_000, 0.05, kept_aside=KEEP
        )
        plan = replace(STILL, monthly_net_income=required, monthly_investment_contribution=required)
        end = project(plan, RETURN_5, START, months, kept_aside=KEEP).at(months)
        assert end.counted == pytest.approx(20_000)

    def test_needed_per_month_with_more_kept_than_held(self):
        """Keeping €12,000 of €10,000 invested: contributions first make up the slice."""
        more = KeptAside(investments=12_000)
        required = calculate_required_monthly_contribution(
            20_000, 24, 10_000, 10_000, 0.05, kept_aside=more
        )
        plan = replace(STILL, monthly_net_income=required, monthly_investment_contribution=required)
        end = project(plan, RETURN_5, START, 24, kept_aside=more).at(24)
        assert end.counted == pytest.approx(20_000)

    def test_keeping_aside_needs_more_per_month(self):
        args = (20_000, 24, 10_000, 10_000, 0.05)
        assert calculate_required_monthly_contribution(*args, kept_aside=KEEP) > (
            calculate_required_monthly_contribution(*args)
        )

    def test_rejects_negative_amounts(self):
        with pytest.raises(InvalidInputError):
            replace(CAR, keep_savings=-1)
        with pytest.raises(InvalidInputError):
            KeptAside(investments=-1)


class TestSimulatedFutures:
    def test_without_volatility_they_match_the_projection(self):
        goal = replace(CAR, **_keep())
        saving = replace(STILL, monthly_net_income=600, monthly_investment_contribution=300)
        futures = simulate_uncertainty(Scenario("Plan"), saving, RETURN_5, goal, START, 0, paths=5)
        plan = run_scenario(Scenario("Plan"), saving, RETURN_5, goal, START)
        assert futures.value_at_target_date.p50 == pytest.approx(
            plan.projected_value_at_target_date
        )
        for level in futures.required_monthly_investment:
            assert level.monthly_amount == pytest.approx(plan.required_monthly_contribution)

    def test_keeping_aside_lowers_the_share_on_time(self):
        """Everything counted: €20,000 today, on time in every future. Keeping €12,000 aside:
        €8,000 plus €480 a month for two years lands near the target, so only some make it."""
        saving = replace(STILL, monthly_net_income=480, monthly_investment_contribution=240)
        kept = simulate_uncertainty(
            Scenario("Plan"), saving, RETURN_5, replace(CAR, **_keep()), START, 0.1, paths=200
        )
        everything = simulate_uncertainty(
            Scenario("Plan"), saving, RETURN_5, CAR, START, 0.1, paths=200
        )
        assert kept.probability_by_target_date < everything.probability_by_target_date


def _keep() -> dict[str, float]:
    return {"keep_savings": KEEP.savings, "keep_investments": KEEP.investments}


def test_the_kept_aside_view_today_and_on_the_target_date():
    """The car example, nothing coming in: €5,000 of savings stays €5,000; €7,000 of
    investments grows for two years at 5% to €7,717.50."""
    result = run_scenario(Scenario("Plan"), STILL, RETURN_5, replace(CAR, **_keep()), START)
    kept = result.kept_aside
    assert (kept.savings_today, kept.investments_today) == (5_000, 7_000)
    assert kept.total_today == 12_000
    assert kept.savings_at_target == 5_000
    assert kept.investments_at_target == pytest.approx(7_000 * 1.05**2)
    assert kept.investment_growth == pytest.approx(7_000 * 1.05**2 - 7_000)
    at_target = result.snapshots[result.months_to_target_date]
    assert kept.total_at_target + result.projected_value_at_target_date == pytest.approx(
        kept.liquid_at_target
    )
    assert kept.liquid_at_target == pytest.approx(at_target.liquid_assets)
    assert run_scenario(Scenario("Plan"), STILL, RETURN_5, CAR, START).kept_aside is None
