"""The stored plan: profile, goals and assumption sets."""

from typing import Annotated

from fastapi import APIRouter, Path, Request, status

from app.agents.plan_draft import apply_extraction, start
from app.agents.providers import RULES
from app.api.deps import SessionDep, TodayDep
from app.schemas.plan import (
    AssumptionSetOut,
    GoalIn,
    GoalOut,
    PlanStatusOut,
    PositionOut,
    Profile,
    ProfileIn,
    ProfileOut,
    Rates,
)
from app.schemas.plan_draft import DraftOut, DraftRequest
from app.services import assumptions, goals, profile
from app.services.plan_status import get_plan_status

router = APIRouter()


@router.post("/plan/draft", tags=["profile"])
def draft_plan(body: DraftRequest, request: Request, today: TodayDep) -> DraftOut:
    """Turn a description ("I take home 2,400 a month…") into a draft of the plan forms, with
    the next question. Nothing is saved and the description isn't stored: the person checks
    the forms and saves them. Send the returned draft back with the next message."""
    if not body.message:
        return DraftOut(**start(body.draft).model_dump(), read_by=RULES)
    read = request.app.state.chat_provider.read_plan(body.message, body.draft.asked)
    reply = apply_extraction(body.draft, read.extraction, today)
    return DraftOut(**reply.model_dump(), read_by=read.source)


def _profile_out(session: SessionDep) -> ProfileOut:
    return ProfileOut(
        profile=Profile.from_domain(profile.get_profile(session)),
        position=PositionOut.from_domain(profile.get_position(session)),
    )


@router.get("/plan/status", tags=["profile"])
def plan_status(session: SessionDep) -> PlanStatusOut:
    """What's saved so far. Projections need both your finances and an active goal."""
    s = get_plan_status(session)
    return PlanStatusOut(has_profile=s.has_profile, has_goal=s.has_goal, ready=s.ready)


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
def create_goal(body: GoalIn, session: SessionDep, today: TodayDep) -> GoalOut:
    """Create a goal. It becomes the active goal; the previous one is kept, inactive.
    The target date must be this month or later, and at most 50 years ahead."""
    return GoalOut.from_saved(goals.create_goal(session, body.to_domain(), today))


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
