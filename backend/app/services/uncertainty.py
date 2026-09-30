"""How sure is a projection: the stored plan run over many simulated futures."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.domain.models import Assumptions, InvestmentRisk
from app.domain.periods import first_of_month
from app.domain.scenarios import Scenario, ScenarioOverrides
from app.domain.uncertainty import (
    DEFAULT_PATHS,
    DEFAULT_SEED,
    REQUIRED_SHARES,
    VOLATILITY,
    UncertaintyResult,
    compare_uncertainty,
    probability_difference,
    simulate_uncertainty,
)
from app.services.assumptions import DEFAULT_ASSUMPTION_SET, get_assumption_set
from app.services.goals import get_active_goal
from app.services.profile import get_profile
from app.services.scenarios import scenarios_to_compare, what_if


@dataclass(frozen=True)
class Uncertainty:
    scenario_name: str
    assumption_set: str
    assumptions: Assumptions
    """Effective assumptions, after overrides."""
    investment_risk: InvestmentRisk
    result: UncertaintyResult


def simulate(
    session: Session,
    today: date,
    overrides: ScenarioOverrides | None = None,
    assumption_set: str = DEFAULT_ASSUMPTION_SET,
    name: str | None = None,
    paths: int = DEFAULT_PATHS,
    seed: int = DEFAULT_SEED,
    required_shares: tuple[float, ...] = REQUIRED_SHARES,
) -> Uncertainty:
    """Simulate the stored plan (optionally with what-if overrides) with random yearly returns
    at the profile's investment risk. The same seed gives the same futures for every plan."""
    scenario = what_if(overrides, name)
    profile = get_profile(session)
    assumptions = get_assumption_set(session, assumption_set).assumptions
    risk = profile.investment_risk
    result = simulate_uncertainty(
        scenario,
        profile,
        assumptions,
        get_active_goal(session).goal,
        first_of_month(today),
        VOLATILITY[risk],
        paths,
        seed,
        required_shares,
    )
    return Uncertainty(
        scenario_name=scenario.name,
        assumption_set=assumption_set,
        assumptions=scenario.overrides.apply(profile, assumptions)[1],
        investment_risk=risk,
        result=result,
    )


@dataclass(frozen=True)
class ComparedFutures:
    scenario: Scenario
    result: UncertaintyResult
    probability_difference: float
    """Share reaching the goal on time, minus the baseline's (the first scenario)."""
    saved_id: int | None


@dataclass(frozen=True)
class FuturesComparison:
    assumption_set: str
    investment_risk: InvestmentRisk
    scenarios: list[ComparedFutures]


def compare(
    session: Session,
    today: date,
    assumption_set: str = DEFAULT_ASSUMPTION_SET,
    scenarios: list[Scenario] | None = None,
    paths: int = DEFAULT_PATHS,
    seed: int = DEFAULT_SEED,
    required_shares: tuple[float, ...] = REQUIRED_SHARES,
) -> FuturesComparison:
    """Simulate the same scenarios as the comparison (by default the built-in ones, then the
    saved ones), all on the same futures. The first scenario is the baseline."""
    profile = get_profile(session)
    assumptions = get_assumption_set(session, assumption_set).assumptions
    scenarios, saved_ids = scenarios_to_compare(session, assumptions, scenarios)
    risk = profile.investment_risk
    results = compare_uncertainty(
        scenarios,
        profile,
        assumptions,
        get_active_goal(session).goal,
        first_of_month(today),
        VOLATILITY[risk],
        paths,
        seed,
        required_shares,
    )
    return FuturesComparison(
        assumption_set=assumption_set,
        investment_risk=risk,
        scenarios=[
            ComparedFutures(
                scenario=scenario,
                result=result,
                probability_difference=probability_difference(result, results[0]),
                saved_id=saved_ids.get(scenario.name),
            )
            for scenario, result in zip(scenarios, results, strict=True)
        ],
    )
