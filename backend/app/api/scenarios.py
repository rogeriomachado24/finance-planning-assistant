"""Projections: simulate the plan, compare scenarios, manage saved scenario definitions."""

from fastapi import APIRouter, Response, status

from app.api.deps import SessionDep, TodayDep
from app.schemas.scenarios import (
    ComparedScenarioOut,
    CompareOut,
    CompareRequest,
    SavedScenarioOut,
    ScenarioIn,
    ScenarioResultOut,
    SimulateRequest,
)
from app.schemas.uncertainty import UncertaintyOut, UncertaintyRequest
from app.services import scenarios, uncertainty

router = APIRouter(tags=["projections"])


@router.post("/simulate")
def simulate(body: SimulateRequest, session: SessionDep, today: TodayDep) -> ScenarioResultOut:
    """Project the saved plan from the start of this month, optionally with what-if overrides.
    Overrides are never saved."""
    result = scenarios.simulate(
        session, today, body.overrides.to_domain(), body.assumption_set, body.name
    )
    return ScenarioResultOut.from_domain(result)


@router.post("/simulate/uncertainty")
def simulate_uncertainty(
    body: UncertaintyRequest, session: SessionDep, today: TodayDep
) -> UncertaintyOut:
    """Run the saved plan (optionally with what-if overrides) over many simulated futures,
    with yearly investment returns varying around the assumed return at the profile's
    investment risk. The same seed always gives the same result."""
    result = uncertainty.simulate(
        session,
        today,
        body.overrides.to_domain(),
        body.assumption_set,
        body.name,
        body.paths,
        body.seed,
    )
    return UncertaintyOut.from_service(result)


@router.post("/scenarios/compare")
def compare(body: CompareRequest, session: SessionDep, today: TodayDep) -> CompareOut:
    """Run several scenarios on the saved plan, side by side. The first scenario is the
    baseline that the differences are measured from (by default, the current plan)."""
    given = None if body.scenarios is None else [s.to_domain() for s in body.scenarios]
    compared = scenarios.compare(session, today, body.assumption_set, given)
    return CompareOut(
        assumption_set=body.assumption_set,
        baseline=compared[0].scenario.name,
        scenarios=[ComparedScenarioOut.from_domain(c) for c in compared],
    )


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
