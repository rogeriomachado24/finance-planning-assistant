"""Plain-language summaries of the pages (Phase 3). The facts come from the same engine runs
as the pages, computed here from the stored plan, never from figures sent by the browser."""

from fastapi import APIRouter, Request

from app.agents.summary import compare_facts, projection_facts
from app.api.deps import SessionDep, TodayDep
from app.schemas.explain import ExplainRequest, SummaryOut
from app.schemas.scenarios import ComparedScenarioOut, ScenarioResultOut
from app.schemas.uncertainty import FuturesComparisonOut, UncertaintyOut
from app.services import scenarios, uncertainty

router = APIRouter(tags=["explain"])


@router.post("/explain/projection")
def explain_projection(
    body: ExplainRequest, request: Request, session: SessionDep, today: TodayDep
) -> SummaryOut:
    """'What does this mean for me?' for the Projection page: when the goal is reached, how
    often on time in simulated futures, and what being on time in 9 of 10 would take. Worded
    by the model when one is available and its text passes the checks."""
    result = ScenarioResultOut.from_domain(
        scenarios.simulate(session, today, assumption_set=body.assumption_set)
    )
    futures = UncertaintyOut.from_service(
        uncertainty.simulate(session, today, assumption_set=body.assumption_set)
    )
    facts = projection_facts(result, futures)
    worded = request.app.state.chat_provider.summarise(facts)
    return SummaryOut(summary=worded.text, facts=facts, worded_by=worded.source)


@router.post("/explain/compare")
def explain_compare(
    body: ExplainRequest, request: Request, session: SessionDep, today: TodayDep
) -> SummaryOut:
    """'What does this mean for me?' for the Compare page: each scenario's difference from the
    current plan, and which reaches the goal earliest or is on time in the most futures."""
    compared = [
        ComparedScenarioOut.from_domain(c)
        for c in scenarios.compare(session, today, body.assumption_set)
    ]
    futures = FuturesComparisonOut.from_service(
        uncertainty.compare(session, today, body.assumption_set)
    )
    facts = compare_facts(compared, futures)
    worded = request.app.state.chat_provider.summarise(facts)
    return SummaryOut(summary=worded.text, facts=facts, worded_by=worded.source)
