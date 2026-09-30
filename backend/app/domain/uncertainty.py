"""Monte Carlo: how sure is a projection? (docs/PHASE2_DESIGN.md, section 2)

Only the investment return is random, drawn once per year. Each simulated future runs the
Phase 1 engine unchanged, with its own sequence of yearly returns. A fixed seed makes the
result reproducible: the same plan always gives the same numbers.

A year's gross return is lognormal, G = exp(X) with X ~ Normal(ln(1 + r), sigma^2), so no
year loses more than everything, and the median future compounds at exactly r: the Phase 1
projection line is the middle of the simulated futures.
"""

import math
import random
from dataclasses import dataclass
from datetime import date

from app.domain.errors import InvalidInputError
from app.domain.goals import months_to_target_date
from app.domain.models import Assumptions, FinancialProfile, Goal, InvestmentRisk
from app.domain.periods import add_months
from app.domain.projection import MAX_PROJECTION_MONTHS, project
from app.domain.scenarios import Scenario

VOLATILITY = {InvestmentRisk.LOW: 0.05, InvestmentRisk.MEDIUM: 0.10, InvestmentRisk.HIGH: 0.15}
"""Yearly volatility (standard deviation of log returns) per risk level. Illustrative."""

DEFAULT_PATHS = 1000
DEFAULT_SEED = 2026
MONTHS_AFTER_TARGET = 120
"""Futures run to the target date plus 10 years (capped at 50 years) to date late goals."""


def sample_yearly_returns(
    rng: random.Random, typical_return: float, volatility: float, years: int
) -> list[float]:
    """One simulated future's returns: lognormal around `typical_return` (the median)."""
    mu = math.log1p(typical_return)
    return [math.expm1(rng.gauss(mu, volatility)) for _ in range(years)]


def percentile(sorted_values: list[float], p: float) -> float:
    """Nearest-rank percentile: the smallest value with at least p% of values at or below it."""
    if not sorted_values:
        raise InvalidInputError("percentile of an empty list")
    rank = max(1, math.ceil(p / 100 * len(sorted_values)))
    return sorted_values[rank - 1]


@dataclass(frozen=True)
class Percentiles:
    p10: float
    p50: float
    p90: float

    @classmethod
    def of(cls, values: list[float]) -> "Percentiles":
        ordered = sorted(values)
        return cls(*(percentile(ordered, p) for p in (10, 50, 90)))


@dataclass(frozen=True)
class GoalDates:
    """Percentiles of the date each future first reaches the target; None means the
    percentile falls among futures that don't reach it within the horizon."""

    p10: date | None
    p50: date | None
    p90: date | None


@dataclass(frozen=True)
class BandPoint:
    month: int
    date: date
    p10: float
    p50: float
    p90: float


@dataclass(frozen=True)
class ReachedBy:
    date: date
    share: float
    """Share of futures that have reached the target at least once by this date."""


@dataclass(frozen=True)
class UncertaintyResult:
    paths: int
    seed: int
    volatility: float
    horizon_months: int
    target_amount: float
    target_date: date
    months_to_target_date: int
    probability_by_target_date: float
    """Share of futures with cash + investments at or above the target on the target date
    (the Monte Carlo version of Phase 1's `reaches_goal`)."""
    probability_margin: float
    """Half-width of the 95% interval of that probability: 1.96 * sqrt(p(1 - p) / n)."""
    goal_dates: GoalDates
    not_reached_share: float
    """Share of futures that don't reach the target within the horizon."""
    value_at_target_date: Percentiles
    shortfall_when_missed: Percentiles | None
    """Among futures below the target on the target date; None when none are."""
    reached_by: tuple[ReachedBy, ...]
    """Each 1 January within the horizon, and the target date."""
    bands: tuple[BandPoint, ...]
    """Cash + investments percentiles for every month, 0..horizon."""


def simulate_uncertainty(
    scenario: Scenario,
    profile: FinancialProfile,
    assumptions: Assumptions,
    goal: Goal,
    start: date,
    volatility: float,
    paths: int = DEFAULT_PATHS,
    seed: int = DEFAULT_SEED,
) -> UncertaintyResult:
    if not 0 <= volatility <= 1:
        raise InvalidInputError(f"volatility must be between 0 and 1; got {volatility}")
    if not 1 <= paths <= 10_000:
        raise InvalidInputError(f"paths must be between 1 and 10,000; got {paths}")

    months_to_target = months_to_target_date(goal.target_date, start)
    horizon = min(MAX_PROJECTION_MONTHS, months_to_target + MONTHS_AFTER_TARGET)
    years = max(1, -(-horizon // 12))
    eff_profile, eff_assumptions = scenario.overrides.apply(profile, assumptions)
    first_year = scenario.overrides.first_year_return
    target = goal.target_amount

    # The same seed draws the same returns for every scenario (common random numbers).
    rng = random.Random(seed)
    series: list[list[float]] = []
    goal_months: list[int | None] = []
    for _ in range(paths):
        returns = sample_yearly_returns(rng, eff_assumptions.annual_return, volatility, years)
        if first_year is not None:
            returns[0] = first_year  # a chosen market drop; later years stay random
        liquid = [
            s.liquid_assets
            for s in project(eff_profile, eff_assumptions, start, horizon, returns).snapshots
        ]
        series.append(liquid)
        goal_months.append(next((m for m, v in enumerate(liquid) if v >= target), None))

    at_target = [liquid[months_to_target] for liquid in series]
    probability = sum(v >= target for v in at_target) / paths
    shortfalls = [target - v for v in at_target if v < target]

    reached_months = sorted(m if m is not None else math.inf for m in goal_months)

    def goal_date(p: float) -> date | None:
        month = percentile(reached_months, p)
        return None if month == math.inf else add_months(start, int(month))

    checkpoints = sorted(
        {m for m in range(1, horizon + 1) if add_months(start, m).month == 1} | {months_to_target}
    )
    return UncertaintyResult(
        paths=paths,
        seed=seed,
        volatility=volatility,
        horizon_months=horizon,
        target_amount=target,
        target_date=goal.target_date,
        months_to_target_date=months_to_target,
        probability_by_target_date=probability,
        probability_margin=1.96 * math.sqrt(probability * (1 - probability) / paths),
        goal_dates=GoalDates(goal_date(10), goal_date(50), goal_date(90)),
        not_reached_share=sum(m is None for m in goal_months) / paths,
        value_at_target_date=Percentiles.of(at_target),
        shortfall_when_missed=Percentiles.of(shortfalls) if shortfalls else None,
        reached_by=tuple(
            ReachedBy(
                add_months(start, m),
                sum(g is not None and g <= m for g in goal_months) / paths,
            )
            for m in checkpoints
        ),
        bands=tuple(
            _band(start, month, list(column))
            for month, column in enumerate(zip(*series, strict=True))
        ),
    )


def _band(start: date, month: int, values: list[float]) -> BandPoint:
    p = Percentiles.of(values)
    return BandPoint(month, add_months(start, month), p.p10, p.p50, p.p90)
