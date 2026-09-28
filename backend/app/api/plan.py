"""The stored plan: profile, goals and assumption sets."""

from typing import Annotated

from fastapi import APIRouter, Path, status

from app.api.deps import SessionDep
from app.schemas.plan import (
    AssumptionSetOut,
    GoalIn,
    GoalOut,
    PositionOut,
    Profile,
    ProfileIn,
    ProfileOut,
    Rates,
)
from app.services import assumptions, goals, profile

router = APIRouter()


def _profile_out(session: SessionDep) -> ProfileOut:
    return ProfileOut(
        profile=Profile.from_domain(profile.get_profile(session)),
        position=PositionOut.from_domain(profile.get_position(session)),
    )


@router.get("/profile", tags=["profile"])
def get_profile(session: SessionDep) -> ProfileOut:
    """The saved profile and today's position (surplus, savings rate, net worth)."""
    return _profile_out(session)


@router.put("/profile", tags=["profile"])
def put_profile(body: ProfileIn, session: SessionDep) -> ProfileOut:
    """Create or replace the profile."""
    profile.save_profile(session, body.to_domain())
    return _profile_out(session)


@router.get("/goals", tags=["goals"])
def list_goals(session: SessionDep) -> list[GoalOut]:
    """All goals: the active one first, then previous ones, newest first."""
    return [GoalOut.from_saved(g) for g in goals.list_goals(session)]


@router.post("/goals", tags=["goals"], status_code=status.HTTP_201_CREATED)
def create_goal(body: GoalIn, session: SessionDep) -> GoalOut:
    """Create a goal. It becomes the active goal; the previous one is kept, inactive."""
    return GoalOut.from_saved(goals.create_goal(session, body.to_domain()))


@router.get("/assumptions", tags=["assumptions"])
def list_assumption_sets(session: SessionDep) -> list[AssumptionSetOut]:
    return [AssumptionSetOut.from_saved(s) for s in assumptions.list_assumption_sets(session)]


@router.put("/assumptions/{name}", tags=["assumptions"])
def put_assumption_set(
    name: Annotated[str, Path(min_length=1, max_length=50)], body: Rates, session: SessionDep
) -> AssumptionSetOut:
    """Create or replace the assumption set with this name (e.g. `base`)."""
    return AssumptionSetOut.from_saved(
        assumptions.save_assumption_set(session, name, body.to_domain())
    )
