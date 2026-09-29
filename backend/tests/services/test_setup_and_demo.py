"""Assumption presets, database preparation and demo data."""

from dataclasses import replace
from datetime import date

import pytest
from sqlalchemy import Engine, inspect
from sqlalchemy.orm import Session

from app.db.session import create_db_engine, create_session_factory
from app.domain.scenarios import Scenario
from app.services.assumptions import (
    ASSUMPTION_PRESETS,
    ensure_assumption_presets,
    get_assumption_set,
    list_assumption_sets,
    save_assumption_set,
)
from app.services.demo import DEMO_PROFILE, has_user_data, load_demo_data
from app.services.errors import ConflictError
from app.services.goals import create_goal, list_goals
from app.services.profile import get_profile, save_profile
from app.services.scenarios import compare, save_scenario
from app.services.setup import prepare_database
from tests.sample_plan import GOAL, TODAY


class TestAssumptionPresets:
    def test_presets_have_the_agreed_values(self):
        rates = {
            name: (
                a.annual_return,
                a.annual_salary_growth,
                a.annual_expense_growth,
                a.annual_inflation,
            )
            for name, a in ASSUMPTION_PRESETS.items()
        }
        assert rates == {
            "conservative": (0.02, 0.01, 0.03, 0.03),
            "base": (0.05, 0.02, 0.02, 0.02),
            "optimistic": (0.07, 0.03, 0.02, 0.02),
        }

    def test_added_once(self, session: Session):
        assert ensure_assumption_presets(session) == ["conservative", "base", "optimistic"]
        assert ensure_assumption_presets(session) == []
        stored = {s.name: s.assumptions for s in list_assumption_sets(session)}
        assert stored == ASSUMPTION_PRESETS

    def test_user_edits_are_never_overwritten(self, session: Session):
        edited = replace(ASSUMPTION_PRESETS["base"], annual_return=0.04)
        save_assumption_set(session, "base", edited)
        assert ensure_assumption_presets(session) == ["conservative", "optimistic"]
        assert get_assumption_set(session, "base").assumptions == edited


def test_prepare_database_builds_an_empty_database(empty_db_url: str):
    engine: Engine = create_db_engine(empty_db_url)
    session_factory = create_session_factory(engine)
    try:
        prepare_database(empty_db_url, session_factory)
        prepare_database(empty_db_url, session_factory)  # safe to run on every start
        assert "goals" in inspect(engine).get_table_names()
        with session_factory() as session:
            assert len(list_assumption_sets(session)) == 3
    finally:
        engine.dispose()


class TestDemoData:
    def test_loads_a_plan_that_can_be_projected(self, session: Session):
        goal = load_demo_data(session, TODAY).goal
        assert goal.target_date == date(2032, 6, 1)
        assert get_profile(session) == DEMO_PROFILE
        names = [r.scenario_name for r in compare(session, TODAY)]
        assert names == ["Current plan", "Higher contribution", "Higher income", "Spend €200 less"]

    def test_goal_is_always_six_years_ahead(self, session: Session):
        goal = load_demo_data(session, date(2040, 3, 15)).goal
        assert goal.target_date == date(2046, 6, 1)

    @pytest.mark.parametrize("existing", ["profile", "goal", "scenario"])
    def test_refuses_to_overwrite_user_data(self, session: Session, existing: str):
        if existing == "profile":
            save_profile(session, replace(DEMO_PROFILE, cash=1))
        elif existing == "goal":
            create_goal(session, GOAL)
        else:
            save_scenario(session, Scenario("Mine"))
        assert has_user_data(session)
        with pytest.raises(ConflictError):
            load_demo_data(session, TODAY)

    def test_reset_replaces_everything(self, session: Session):
        save_profile(session, replace(DEMO_PROFILE, cash=1))
        create_goal(session, GOAL)
        save_assumption_set(
            session, "base", replace(ASSUMPTION_PRESETS["base"], annual_return=0.04)
        )
        save_scenario(session, Scenario("Mine"))

        load_demo_data(session, TODAY, reset=True)

        assert get_profile(session) == DEMO_PROFILE
        assert [g.goal.name for g in list_goals(session)] == ["Buy a house"]
        assert get_assumption_set(session, "base").assumptions == ASSUMPTION_PRESETS["base"]
