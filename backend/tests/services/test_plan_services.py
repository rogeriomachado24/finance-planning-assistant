"""Profile, goals and assumption sets: storing and loading the plan."""

from dataclasses import replace
from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import FinancialProfileRecord
from app.domain.errors import InvalidInputError
from app.domain.models import Assumptions, Goal
from app.services.assumptions import (
    get_assumption_set,
    list_assumption_sets,
    save_assumption_set,
)
from app.services.errors import NotFoundError
from app.services.goals import create_goal, get_active_goal, list_goals
from app.services.profile import get_position, get_profile, save_profile
from tests.sample_plan import BASE, GOAL, PROFILE


class TestProfile:
    def test_missing_profile_is_reported(self, session: Session):
        with pytest.raises(NotFoundError):
            get_profile(session)

    def test_saved_profile_is_loaded_back(self, session: Session):
        save_profile(session, PROFILE)
        assert get_profile(session) == PROFILE

    def test_saving_again_replaces_the_single_profile(self, session: Session):
        save_profile(session, PROFILE)
        save_profile(session, replace(PROFILE, cash=12_000))
        assert get_profile(session).cash == 12_000
        assert session.scalar(select(func.count()).select_from(FinancialProfileRecord)) == 1

    def test_returns_the_profile_as_stored(self, session: Session):
        stored = save_profile(session, replace(PROFILE, cash=100.005))
        assert stored.cash == 100.01

    def test_position_is_computed_by_the_domain(self, session: Session):
        save_profile(session, PROFILE)
        position = get_position(session)
        assert position.monthly_surplus == 800
        assert position.savings_rate == 0.32
        assert position.net_worth == 25_000


class TestGoals:
    def test_missing_active_goal_is_reported(self, session: Session):
        with pytest.raises(NotFoundError):
            get_active_goal(session)

    def test_new_goal_becomes_the_active_one(self, session: Session):
        first = create_goal(session, GOAL)
        second = create_goal(session, Goal("Buy a car", 15_000, date(2028, 1, 1)))

        assert get_active_goal(session) == second
        assert [(g.id, g.is_active) for g in list_goals(session)] == [
            (second.id, True),
            (first.id, False),
        ]
        assert list_goals(session)[1].goal == GOAL


class TestAssumptionSets:
    def test_missing_set_is_reported(self, session: Session):
        with pytest.raises(NotFoundError, match="'optimistic'"):
            get_assumption_set(session, "optimistic")

    def test_sets_are_saved_and_replaced_by_name(self, session: Session):
        save_assumption_set(session, "base", BASE)
        save_assumption_set(session, "optimistic", replace(BASE, annual_return=0.07))
        save_assumption_set(session, "base", replace(BASE, annual_return=0.045))

        assert [s.name for s in list_assumption_sets(session)] == ["base", "optimistic"]
        assert get_assumption_set(session, "base").assumptions.annual_return == 0.045
        assert get_assumption_set(session, "optimistic").assumptions.annual_return == 0.07

    def test_name_is_required(self, session: Session):
        with pytest.raises(InvalidInputError):
            save_assumption_set(session, "  ", Assumptions())
