from dataclasses import replace
from datetime import date

import pytest

from app.domain.errors import InvalidInputError
from app.domain.models import Assumptions, FinancialProfile
from app.domain.projection import WarningCode, project
from app.domain.scenarios import (
    Scenario,
    ScenarioOverrides,
    compare_scenarios,
    default_scenarios,
    delta_from_baseline,
    run_scenario,
)


class TestOverrides:
    def test_empty_overrides_keep_everything(self, profile, assumptions):
        assert ScenarioOverrides().apply(profile, assumptions) == (profile, assumptions)

    def test_contribution_delta(self, profile, assumptions):
        new_profile, _ = ScenarioOverrides(monthly_investment_contribution_delta=200).apply(
            profile, assumptions
        )
        assert new_profile.monthly_investment_contribution == 600

    def test_absolute_contribution_and_rates(self, profile, assumptions):
        overrides = ScenarioOverrides(
            monthly_investment_contribution=650,
            monthly_expenses=1800,
            annual_return=0.03,
            annual_salary_growth=0.05,
        )
        new_profile, new_assumptions = overrides.apply(profile, assumptions)
        assert new_profile.monthly_investment_contribution == 650
        assert new_profile.monthly_expenses == 1800
        assert new_assumptions.annual_return == 0.03
        assert new_assumptions.annual_salary_growth == 0.05
        assert new_assumptions.annual_inflation == assumptions.annual_inflation

    def test_income_and_expense_deltas(self, profile, assumptions):
        overrides = ScenarioOverrides(monthly_net_income_delta=300, monthly_expenses_delta=-200)
        new_profile, _ = overrides.apply(profile, assumptions)
        assert new_profile.monthly_net_income == 2800
        assert new_profile.monthly_expenses == 1500

    @pytest.mark.parametrize("name", ["monthly_net_income", "monthly_expenses"])
    def test_rejects_absolute_and_delta_for_any_amount(self, name):
        with pytest.raises(InvalidInputError, match=f"set either {name} or its delta"):
            ScenarioOverrides(**{name: 1000, f"{name}_delta": 100})

    def test_rejects_delta_that_makes_expenses_negative(self, profile, assumptions):
        with pytest.raises(InvalidInputError):
            ScenarioOverrides(monthly_expenses_delta=-5000).apply(profile, assumptions)

    def test_does_not_modify_the_inputs(self, profile, assumptions):
        ScenarioOverrides(monthly_investment_contribution_delta=200).apply(profile, assumptions)
        assert profile.monthly_investment_contribution == 400

    def test_rejects_absolute_and_delta_together(self):
        with pytest.raises(InvalidInputError):
            ScenarioOverrides(
                monthly_investment_contribution=500, monthly_investment_contribution_delta=100
            )

    def test_rejects_delta_that_makes_contribution_negative(self, profile, assumptions):
        with pytest.raises(InvalidInputError):
            ScenarioOverrides(monthly_investment_contribution_delta=-500).apply(
                profile, assumptions
            )

    def test_rejects_invalid_rate(self, profile, assumptions):
        with pytest.raises(InvalidInputError):
            ScenarioOverrides(annual_return=7).apply(profile, assumptions)

    def test_rejects_invalid_market_drop(self):
        with pytest.raises(InvalidInputError):
            ScenarioOverrides(first_year_return=-1)

    def test_market_drop_replaces_only_the_first_year(self, assumptions):
        overrides = ScenarioOverrides(first_year_return=-0.30)
        assert overrides.yearly_returns(assumptions, 3) == [-0.30, 0.05, 0.05]
        assert ScenarioOverrides().yearly_returns(assumptions, 3) is None


class TestRunScenario:
    def test_current_plan_reaches_goal(self, profile, assumptions, goal, start):
        result = run_scenario(Scenario("Current plan"), profile, assumptions, goal, start)
        assert result.scenario_name == "Current plan"
        assert result.monthly_contribution == 400
        assert result.monthly_surplus == 800
        assert result.target_amount == 80_000
        assert result.months_to_target_date == 68
        assert result.reaches_goal
        assert result.shortfall == 0
        assert result.projected_value_at_target_date >= 80_000
        assert result.projected_goal_date <= goal.target_date

    def test_goal_progress_is_measured_from_today(self, profile, assumptions, goal, start):
        """€10,000 cash + €15,000 invested towards €80,000."""
        progress = run_scenario(
            Scenario("Current plan"), profile, assumptions, goal, start
        ).goal_progress
        assert progress.current_amount == 25_000
        assert progress.remaining == 55_000
        assert progress.fraction == 0.3125

    def test_value_at_target_date_matches_the_projection(self, profile, assumptions, goal, start):
        result = run_scenario(Scenario("Current plan"), profile, assumptions, goal, start)
        expected = project(profile, assumptions, start, 68).at(68).liquid_assets
        assert result.projected_value_at_target_date == pytest.approx(expected)

    def test_market_drop_lowers_the_outcome(self, profile, assumptions, goal, start):
        """30% off €15,000 invested (plus a year of contributions) in the first year."""
        plan = run_scenario(Scenario("Current plan"), profile, assumptions, goal, start)
        drop = run_scenario(
            Scenario("Drop", ScenarioOverrides(first_year_return=-0.30)),
            profile,
            assumptions,
            goal,
            start,
        )
        assert drop.projected_value_at_target_date < plan.projected_value_at_target_date
        assert drop.months_to_goal > plan.months_to_goal
        assert drop.required_monthly_contribution > plan.required_monthly_contribution
        assert drop.snapshots[12].investments < plan.snapshots[12].investments * 0.75

    def test_shortfall_when_goal_is_missed(self, profile, assumptions, goal, start):
        big_goal = replace(goal, target_amount=150_000)
        result = run_scenario(Scenario("Current plan"), profile, assumptions, big_goal, start)
        assert not result.reaches_goal
        assert result.shortfall == pytest.approx(150_000 - result.projected_value_at_target_date)
        assert result.projected_goal_date > big_goal.target_date
        assert result.required_monthly_contribution > profile.monthly_investment_contribution

    def test_series_runs_to_the_later_of_target_and_goal_date(
        self, profile, assumptions, goal, start
    ):
        big_goal = replace(goal, target_amount=150_000)
        result = run_scenario(Scenario("Current plan"), profile, assumptions, big_goal, start)
        assert result.snapshots[-1].month == result.months_to_goal
        assert result.snapshots[-1].liquid_assets >= 150_000

    def test_unreachable_goal(self, goal, start):
        profile = FinancialProfile(monthly_net_income=2000, monthly_expenses=2000)
        result = run_scenario(Scenario("Current plan"), profile, Assumptions(), goal, start)
        assert result.projected_goal_date is None
        assert result.months_to_goal is None
        assert not result.reaches_goal
        assert result.shortfall == 80_000
        assert result.snapshots[-1].month == result.months_to_target_date

    def test_goal_already_reached(self, assumptions, goal, start):
        profile = FinancialProfile(monthly_net_income=2000, monthly_expenses=1500, cash=90_000)
        result = run_scenario(Scenario("Current plan"), profile, assumptions, goal, start)
        assert result.months_to_goal == 0
        assert result.projected_goal_date == start
        assert result.required_monthly_contribution == 0

    def test_only_warnings_within_the_series_are_reported(self, goal, start):
        # Surplus turns negative after a few years; the target date comes first.
        profile = FinancialProfile(monthly_net_income=2000, monthly_expenses=1900, cash=1000)
        near_goal = replace(goal, target_amount=2000, target_date=date(2027, 10, 1))
        result = run_scenario(
            Scenario("Current plan"),
            profile,
            Assumptions(annual_expense_growth=0.05),
            near_goal,
            start,
        )
        assert all(w.month <= result.snapshots[-1].month for w in result.warnings)
        assert WarningCode.LIQUID_FUNDS_EXHAUSTED not in {w.code for w in result.warnings}

    def test_rejects_target_date_before_start(self, profile, assumptions, goal, start):
        past_goal = replace(goal, target_date=date(2026, 1, 1))
        with pytest.raises(InvalidInputError):
            run_scenario(Scenario("Current plan"), profile, assumptions, past_goal, start)

    def test_target_date_in_the_current_month(self, profile, assumptions, goal, start):
        result = run_scenario(
            Scenario("Current plan"), profile, assumptions, replace(goal, target_date=start), start
        )
        assert result.months_to_target_date == 0
        assert result.projected_value_at_target_date == profile.liquid_assets
        assert result.required_monthly_contribution is None


class TestScenarioComparison:
    def test_default_scenarios(self, assumptions):
        scenarios = default_scenarios(replace(assumptions, annual_salary_growth=0.02))
        assert [s.name for s in scenarios] == [
            "Current plan",
            "Higher contribution",
            "Higher income",
        ]
        assert scenarios[1].overrides.monthly_investment_contribution_delta == 100
        assert scenarios[2].overrides.annual_salary_growth == pytest.approx(0.04)

    def test_levers_reach_the_goal_no_later_than_the_current_plan(
        self, profile, assumptions, goal, start
    ):
        big_goal = replace(goal, target_amount=120_000)
        current, higher_contribution, higher_income = compare_scenarios(
            default_scenarios(assumptions), profile, assumptions, big_goal, start
        )
        assert higher_contribution.monthly_contribution == 500
        assert higher_contribution.months_to_goal <= current.months_to_goal
        assert higher_income.months_to_goal < current.months_to_goal
        assert (
            higher_contribution.projected_value_at_target_date
            > current.projected_value_at_target_date
        )


class TestDeltaFromBaseline:
    def test_baseline_against_itself_is_zero(self, profile, assumptions, goal, start):
        current = run_scenario(Scenario("Current plan"), profile, assumptions, goal, start)
        delta = delta_from_baseline(current, current)
        assert (delta.goal_months_earlier, delta.value_at_target_difference) == (0, 0)

    def test_more_invested_is_earlier_and_higher(self, profile, assumptions, goal, start):
        current = run_scenario(Scenario("Current plan"), profile, assumptions, goal, start)
        more = run_scenario(
            Scenario("More", ScenarioOverrides(monthly_net_income=4000)),
            profile,
            assumptions,
            goal,
            start,
        )
        delta = delta_from_baseline(more, current)
        assert delta.goal_months_earlier == current.months_to_goal - more.months_to_goal > 0
        assert delta.value_at_target_difference == pytest.approx(
            more.projected_value_at_target_date - current.projected_value_at_target_date
        )
        assert delta_from_baseline(current, more).goal_months_earlier < 0

    def test_unknown_when_a_goal_is_never_reached(self, profile, assumptions, goal, start):
        current = run_scenario(Scenario("Current plan"), profile, assumptions, goal, start)
        broke = run_scenario(
            Scenario(
                "Broke", ScenarioOverrides(monthly_net_income=0, monthly_investment_contribution=0)
            ),
            profile,
            assumptions,
            goal,
            start,
        )
        assert broke.months_to_goal is None
        assert delta_from_baseline(broke, current).goal_months_earlier is None
