"""Demo data for trying the app: the sample person used throughout the docs."""

from datetime import date

from sqlalchemy import delete, exists, select
from sqlalchemy.orm import Session

from app.db.models import AssumptionSetRecord, FinancialProfileRecord, GoalRecord, ScenarioRecord
from app.domain.models import FinancialProfile, Goal, GoalType
from app.domain.scenarios import Scenario, ScenarioOverrides
from app.services.assumptions import ensure_assumption_presets
from app.services.errors import ConflictError
from app.services.goals import SavedGoal, create_goal
from app.services.profile import save_profile
from app.services.scenarios import save_scenario

DEMO_PROFILE = FinancialProfile(
    monthly_net_income=2500,
    monthly_expenses=1700,
    cash=10_000,
    investments=15_000,
    monthly_investment_contribution=400,
    age=32,
)

DEMO_SCENARIOS = [
    Scenario(
        "Spend €200 less",
        ScenarioOverrides(monthly_expenses=1500),
        "Monthly expenses of 1,500 EUR instead of 1,700.",
    ),
]


def demo_goal(today: date) -> Goal:
    """A house deposit due in June, six years from now (so the demo never expires)."""
    return Goal(
        name="Buy a house",
        target_amount=80_000,
        target_date=date(today.year + 6, 6, 1),
        goal_type=GoalType.HOUSE,
        description="Deposit for a first home.",
    )


def has_user_data(session: Session) -> bool:
    """True once a profile, goal or saved scenario exists. Assumption presets don't count."""
    return any(
        session.scalar(select(exists().select_from(table)))
        for table in (FinancialProfileRecord, GoalRecord, ScenarioRecord)
    )


def clear_all_data(session: Session) -> None:
    for table in (ScenarioRecord, GoalRecord, FinancialProfileRecord, AssumptionSetRecord):
        session.execute(delete(table))
    session.commit()


def load_demo_data(session: Session, today: date, reset: bool = False) -> SavedGoal:
    """Store the demo profile, goal, saved scenarios and the assumption presets.

    Refuses to touch a database that already holds user data, unless `reset` is set,
    in which case everything (including edited assumption sets) is deleted first.
    """
    if reset:
        clear_all_data(session)
    elif has_user_data(session):
        raise ConflictError("the database already contains a profile, goal or saved scenario")

    ensure_assumption_presets(session)
    save_profile(session, DEMO_PROFILE)
    goal = create_goal(session, demo_goal(today))
    for scenario in DEMO_SCENARIOS:
        save_scenario(session, scenario)
    return goal
