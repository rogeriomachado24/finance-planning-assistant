from dataclasses import dataclass
from datetime import date

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import GoalRecord
from app.domain.goals import months_to_target_date
from app.domain.models import Goal
from app.domain.periods import first_of_month
from app.services.errors import NotFoundError
from app.services.mapping import goal_from_record, goal_to_record


@dataclass(frozen=True)
class SavedGoal:
    id: int
    goal: Goal
    is_active: bool


def _saved(record: GoalRecord) -> SavedGoal:
    return SavedGoal(id=record.id, goal=goal_from_record(record), is_active=record.is_active)


def list_goals(session: Session) -> list[SavedGoal]:
    """Active goal first, then previous goals, newest first."""
    records = session.scalars(
        select(GoalRecord).order_by(GoalRecord.is_active.desc(), GoalRecord.id.desc())
    )
    return [_saved(r) for r in records]


def get_active_goal(session: Session) -> SavedGoal:
    record = session.scalar(select(GoalRecord).where(GoalRecord.is_active))
    if record is None:
        raise NotFoundError("no active goal has been saved yet")
    return _saved(record)


def create_goal(session: Session, goal: Goal, today: date) -> SavedGoal:
    """Save a new goal as the active one. The previous active goal is kept, but deactivated.

    The target date must fall within the projection horizon starting this month, so a saved
    goal can always be projected.
    """
    months_to_target_date(goal.target_date, first_of_month(today))
    session.execute(update(GoalRecord).where(GoalRecord.is_active).values(is_active=False))
    record = goal_to_record(goal)
    session.add(record)
    session.commit()
    return _saved(record)
