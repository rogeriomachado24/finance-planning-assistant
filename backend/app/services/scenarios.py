"""Saved scenario definitions, and running projections against the stored plan.

Projections are read-only: overrides are applied to copies, never saved to the profile.
"""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ScenarioRecord
from app.domain.errors import InvalidInputError
from app.domain.models import Assumptions
from app.domain.periods import first_of_month
from app.domain.scenarios import (
    Scenario,
    ScenarioOverrides,
    ScenarioResult,
    compare_scenarios,
    default_scenarios,
    run_scenario,
)
from app.services.assumptions import DEFAULT_ASSUMPTION_SET, get_assumption_set
from app.services.errors import NotFoundError
from app.services.goals import get_active_goal
from app.services.mapping import overrides_from_dict, overrides_to_dict
from app.services.profile import get_profile

CURRENT_PLAN = "Current plan"
RESERVED_NAMES = frozenset(s.name for s in default_scenarios(Assumptions()))


@dataclass(frozen=True)
class SavedScenario:
    id: int
    scenario: Scenario


def _saved(record: ScenarioRecord) -> SavedScenario:
    scenario = Scenario(
        name=record.name,
        overrides=overrides_from_dict(record.overrides),
        description=record.description or "",
    )
    return SavedScenario(id=record.id, scenario=scenario)


def list_scenarios(session: Session) -> list[SavedScenario]:
    records = session.scalars(select(ScenarioRecord).order_by(ScenarioRecord.id))
    return [_saved(r) for r in records]


def save_scenario(session: Session, scenario: Scenario) -> SavedScenario:
    """Create or replace the saved scenario with this name."""
    name = scenario.name.strip()
    if not name:
        raise InvalidInputError("scenario name must not be empty")
    if name in RESERVED_NAMES:
        raise InvalidInputError(f"{name!r} is a built-in scenario name")
    record = session.scalar(select(ScenarioRecord).where(ScenarioRecord.name == name))
    if record is None:
        record = ScenarioRecord(name=name)
        session.add(record)
    record.overrides = overrides_to_dict(scenario.overrides)
    record.description = scenario.description or None
    session.commit()
    return _saved(record)


def delete_scenario(session: Session, scenario_id: int) -> None:
    record = session.get(ScenarioRecord, scenario_id)
    if record is None:
        raise NotFoundError(f"no saved scenario with id {scenario_id}")
    session.delete(record)
    session.commit()


def simulate(
    session: Session,
    today: date,
    overrides: ScenarioOverrides | None = None,
    assumption_set: str = DEFAULT_ASSUMPTION_SET,
    name: str = CURRENT_PLAN,
) -> ScenarioResult:
    """Project the stored plan, optionally with what-if overrides, from the start of this month."""
    scenario = Scenario(name, overrides or ScenarioOverrides())
    return run_scenario(
        scenario,
        get_profile(session),
        get_assumption_set(session, assumption_set).assumptions,
        get_active_goal(session).goal,
        first_of_month(today),
    )


def compare(
    session: Session,
    today: date,
    assumption_set: str = DEFAULT_ASSUMPTION_SET,
    scenarios: list[Scenario] | None = None,
) -> list[ScenarioResult]:
    """Run several scenarios on the stored plan. By default: the built-in scenarios
    (current plan, higher contribution, higher income) followed by the saved ones."""
    assumptions = get_assumption_set(session, assumption_set).assumptions
    if scenarios is None:
        scenarios = default_scenarios(assumptions) + [s.scenario for s in list_scenarios(session)]
    return compare_scenarios(
        scenarios,
        get_profile(session),
        assumptions,
        get_active_goal(session).goal,
        first_of_month(today),
    )
