import pytest
from sqlalchemy.orm import Session

from app.services.assumptions import save_assumption_set
from app.services.goals import create_goal
from app.services.profile import save_profile
from tests.sample_plan import BASE, GOAL, PROFILE


@pytest.fixture
def plan(session: Session) -> Session:
    """A database holding the sample profile, the base assumption set and an active goal."""
    save_profile(session, PROFILE)
    save_assumption_set(session, "base", BASE)
    create_goal(session, GOAL)
    return session
