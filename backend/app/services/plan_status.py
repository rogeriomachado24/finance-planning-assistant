"""What's stored so far: the UI uses it to guide a new user through setting up their plan."""

from dataclasses import dataclass

from sqlalchemy import delete, exists, select
from sqlalchemy.orm import Session

from app.db.models import SINGLE_PROFILE_ID, FinancialProfileRecord, GoalRecord, ScenarioRecord


@dataclass(frozen=True)
class PlanStatus:
    has_profile: bool
    has_goal: bool
    """An active goal; previous goals don't count."""

    @property
    def ready(self) -> bool:
        """Projections need both (assumption presets always exist)."""
        return self.has_profile and self.has_goal


def get_plan_status(session: Session) -> PlanStatus:
    return PlanStatus(
        has_profile=session.get(FinancialProfileRecord, SINGLE_PROFILE_ID) is not None,
        has_goal=bool(session.scalar(select(exists().where(GoalRecord.is_active)))),
    )


def start_fresh(session: Session) -> None:
    """Delete the finances, every goal and the saved scenarios: a new plan from scratch. The
    assumption sets stay (they are views about the future, not facts about the person)."""
    for table in (ScenarioRecord, GoalRecord, FinancialProfileRecord):
        session.execute(delete(table))
    session.commit()
