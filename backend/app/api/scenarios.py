"""Projections: simulate the plan, compare scenarios, manage saved scenario definitions."""

from fastapi import APIRouter, Response, status

from app.api.deps import SessionDep, TodayDep
from app.schemas.scenarios import (
    CompareRequest,
    SavedScenarioOut,
    ScenarioIn,
    ScenarioResultOut,
    SimulateRequest,
)
from app.services import scenarios

router = APIRouter(tags=["projections"])


@router.post("/simulate")
def simulate(body: SimulateRequest, session: SessionDep, today: TodayDep) -> ScenarioResultOut:
    """Project the saved plan from the start of this month, optionally with what-if overrides.
    Overrides are never saved."""
    result = scenarios.simulate(
        session, today, body.overrides.to_domain(), body.assumption_set, body.name
    )
    return ScenarioResultOut.from_domain(result)


@router.post("/scenarios/compare")
def compare(body: CompareRequest, session: SessionDep, today: TodayDep) -> list[ScenarioResultOut]:
    """Run several scenarios on the saved plan, side by side."""
    given = None if body.scenarios is None else [s.to_domain() for s in body.scenarios]
    results = scenarios.compare(session, today, body.assumption_set, given)
    return [ScenarioResultOut.from_domain(r) for r in results]


@router.get("/scenarios")
def list_scenarios(session: SessionDep) -> list[SavedScenarioOut]:
    """Saved scenario definitions (the built-in ones are not listed)."""
    return [SavedScenarioOut.from_saved(s) for s in scenarios.list_scenarios(session)]


@router.post("/scenarios", status_code=status.HTTP_201_CREATED)
def save_scenario(body: ScenarioIn, session: SessionDep) -> SavedScenarioOut:
    """Save a scenario definition. A scenario with the same name is replaced."""
    return SavedScenarioOut.from_saved(scenarios.save_scenario(session, body.to_domain()))


@router.delete("/scenarios/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scenario(scenario_id: int, session: SessionDep) -> Response:
    scenarios.delete_scenario(session, scenario_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
