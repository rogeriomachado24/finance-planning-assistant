"""Simulations and scenario comparisons run on the stored plan."""

from dataclasses import replace
from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.domain.errors import InvalidInputError
from app.domain.scenarios import Scenario, ScenarioOverrides, run_scenario
from app.services.assumptions import save_assumption_set
from app.services.errors import NotFoundError
from app.services.goals import create_goal
from app.services.profile import get_profile, save_profile
from app.services.scenarios import (
    compare,
    delete_scenario,
    list_scenarios,
    save_scenario,
    simulate,
)
from tests.sample_plan import BASE, GOAL, PROFILE, TODAY

MORE_INVESTED = ScenarioOverrides(monthly_investment_contribution_delta=200)


class TestSimulate:
    def test_matches_the_domain_engine_exactly(self, plan: Session):
        """The service only loads data: the numbers are the engine's, unchanged."""
        expected = run_scenario(
            Scenario("Current plan"), PROFILE, BASE, GOAL, start=date(2026, 10, 1)
        )
        assert simulate(plan, TODAY) == expected

    def test_default_names(self, plan: Session):
        assert simulate(plan, TODAY).scenario_name == "Current plan"
        assert simulate(plan, TODAY, MORE_INVESTED).scenario_name == "What-if"

    def test_starts_on_the_first_of_the_current_month(self, plan: Session):
        assert simulate(plan, TODAY).snapshots[0].date == date(2026, 10, 1)

    def test_what_if_does_not_change_the_saved_profile(self, plan: Session):
        result = simulate(plan, TODAY, MORE_INVESTED, name="What if")
        assert result.scenario_name == "What if"
        assert result.monthly_contribution == 600
        assert get_profile(plan) == PROFILE

    def test_uses_the_requested_assumption_set(self, plan: Session):
        save_assumption_set(plan, "conservative", replace(BASE, annual_return=0.02))
        base = simulate(plan, TODAY)
        conservative = simulate(plan, TODAY, assumption_set="conservative")
        assert conservative.assumptions.annual_return == 0.02
        assert conservative.projected_value_at_target_date < base.projected_value_at_target_date

    @pytest.mark.parametrize("missing", ["profile", "goal", "assumptions"])
    def test_reports_what_is_missing(self, session: Session, missing: str):
        if missing != "profile":
            save_profile(session, PROFILE)
        if missing != "goal":
            create_goal(session, GOAL, TODAY)
        if missing != "assumptions":
            save_assumption_set(session, "base", BASE)
        with pytest.raises(NotFoundError):
            simulate(session, TODAY)


class TestCompare:
    def test_runs_built_in_then_saved_scenarios(self, plan: Session):
        save_scenario(plan, Scenario("Invest 200 more", MORE_INVESTED))
        names = [r.scenario_name for r in compare(plan, TODAY)]
        assert names == ["Current plan", "Higher contribution", "Higher income", "Invest 200 more"]

    def test_runs_only_the_given_scenarios(self, plan: Session):
        results = compare(plan, TODAY, scenarios=[Scenario("Only this", MORE_INVESTED)])
        assert [r.scenario_name for r in results] == ["Only this"]


class TestSavedScenarios:
    def test_saved_by_name_and_replaced(self, plan: Session):
        save_scenario(plan, Scenario("Extra", MORE_INVESTED, "Invest more"))
        replaced = save_scenario(plan, Scenario("Extra", ScenarioOverrides(annual_return=0.03)))

        assert [s.scenario for s in list_scenarios(plan)] == [replaced.scenario]
        assert replaced.scenario.overrides == ScenarioOverrides(annual_return=0.03)
        assert replaced.scenario.description == ""

    def test_built_in_names_are_reserved(self, plan: Session):
        with pytest.raises(InvalidInputError, match="built-in"):
            save_scenario(plan, Scenario("Higher income"))

    def test_delete(self, plan: Session):
        saved = save_scenario(plan, Scenario("Extra", MORE_INVESTED))
        delete_scenario(plan, saved.id)
        assert list_scenarios(plan) == []
        with pytest.raises(NotFoundError):
            delete_scenario(plan, saved.id)
