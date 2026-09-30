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
    ScenarioDelta,
    ScenarioOverrides,
    ScenarioResult,
    compare_scenarios,
    default_scenarios,
    delta_from_baseline,
    run_scenario,
)
from app.services.assumptions import DEFAULT_ASSUMPTION_SET, get_assumption_set
from app.services.errors import NotFoundError
from app.services.goals import get_active_goal
from app.services.mapping import overrides_from_dict, overrides_to_dict
from app.services.profile import get_profile

CURRENT_PLAN = "Current plan"
WHAT_IF = "What-if"
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


def what_if(overrides: ScenarioOverrides | None, name: str | None) -> Scenario:
    """Unnamed scenarios are called "Current plan", or "What-if" when overrides are given."""
    overrides = overrides or ScenarioOverrides()
    if name is None:
        name = CURRENT_PLAN if overrides == ScenarioOverrides() else WHAT_IF
    return Scenario(name, overrides)


def simulate(
    session: Session,
    today: date,
    overrides: ScenarioOverrides | None = None,
    assumption_set: str = DEFAULT_ASSUMPTION_SET,
    name: str | None = None,
) -> ScenarioResult:
    """Project the stored plan, optionally with what-if overrides, from the start of this month."""
    return run_scenario(
        what_if(overrides, name),
        get_profile(session),
        get_assumption_set(session, assumption_set).assumptions,
        get_active_goal(session).goal,
        first_of_month(today),
    )


@dataclass(frozen=True)
class ComparedScenario:
    scenario: Scenario
    result: ScenarioResult
    vs_baseline: ScenarioDelta
    """Difference from the first scenario in the comparison (the baseline)."""
    saved_id: int | None
    """Set for saved scenarios, None for built-in or ad-hoc ones."""


def scenarios_to_compare(
    session: Session, assumptions: Assumptions, scenarios: list[Scenario] | None
) -> tuple[list[Scenario], dict[str, int]]:
    """The given scenarios, or by default the built-in ones followed by the saved ones; and
    the ids of the saved ones by name."""
    saved_ids: dict[str, int] = {}
    if scenarios is None:
        saved = list_scenarios(session)
        saved_ids = {s.scenario.name: s.id for s in saved}
        scenarios = default_scenarios(assumptions) + [s.scenario for s in saved]
    if not scenarios:
        raise InvalidInputError("at least one scenario is needed to compare")
    return scenarios, saved_ids


def compare(
    session: Session,
    today: date,
    assumption_set: str = DEFAULT_ASSUMPTION_SET,
    scenarios: list[Scenario] | None = None,
) -> list[ComparedScenario]:
    """Run several scenarios on the stored plan; the first one is the baseline. By default:
    the built-in scenarios (current plan first), followed by the saved ones."""
    assumptions = get_assumption_set(session, assumption_set).assumptions
    scenarios, saved_ids = scenarios_to_compare(session, assumptions, scenarios)
    results = compare_scenarios(
        scenarios,
        get_profile(session),
        assumptions,
        get_active_goal(session).goal,
        first_of_month(today),
    )
    baseline = results[0]
    return [
        ComparedScenario(
            scenario=scenario,
            result=result,
            vs_baseline=delta_from_baseline(result, baseline),
            saved_id=saved_ids.get(scenario.name),
        )
        for scenario, result in zip(scenarios, results, strict=True)
    ]
