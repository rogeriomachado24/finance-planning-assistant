"""How sure is a projection: the stored plan run over many simulated futures."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.domain.models import Assumptions, InvestmentRisk
from app.domain.periods import first_of_month
from app.domain.scenarios import ScenarioOverrides
from app.domain.uncertainty import (
    DEFAULT_PATHS,
    DEFAULT_SEED,
    VOLATILITY,
    UncertaintyResult,
    simulate_uncertainty,
)
from app.services.assumptions import DEFAULT_ASSUMPTION_SET, get_assumption_set
from app.services.goals import get_active_goal
from app.services.profile import get_profile
from app.services.scenarios import what_if


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
    )
    return Uncertainty(
        scenario_name=scenario.name,
        assumption_set=assumption_set,
        assumptions=scenario.overrides.apply(profile, assumptions)[1],
        investment_risk=risk,
        result=result,
    )
