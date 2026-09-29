"""Execute a parsed intent with the services. No language model is involved here.

Every projection intent is run as a comparison, so what-ifs come back with their
difference from the current plan already computed by the domain.
"""

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.agents.intents import (
    CompareScenarios,
    ExplainAssumptions,
    GoalDate,
    RequiredContribution,
    RunProjection,
    WhatIf,
)
from app.domain.models import Assumptions
from app.domain.scenarios import Scenario
from app.services.assumptions import get_assumption_set
from app.services.scenarios import CURRENT_PLAN, WHAT_IF, ComparedScenario, compare

Answerable = (
    RunProjection | GoalDate | RequiredContribution | WhatIf | CompareScenarios | ExplainAssumptions
)


@dataclass(frozen=True)
class IntentOutcome:
    assumption_set: str
    assumptions: Assumptions
    results: list[ComparedScenario]


def run_intent(
    session: Session, intent: Answerable, today: date, default_set: str
) -> IntentOutcome:
    assumption_set = intent.assumption_set or default_set
    assumptions = get_assumption_set(session, assumption_set).assumptions

    match intent:
        case ExplainAssumptions():
            results = []
        case WhatIf(overrides=overrides):
            scenarios = [Scenario(CURRENT_PLAN), Scenario(WHAT_IF, overrides.to_domain())]
            results = compare(session, today, assumption_set, scenarios)
        case CompareScenarios():
            results = compare(session, today, assumption_set)
        case _:
            results = compare(session, today, assumption_set, [Scenario(CURRENT_PLAN)])

    return IntentOutcome(assumption_set, assumptions, results)
