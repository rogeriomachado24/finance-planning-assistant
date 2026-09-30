"""Monte Carlo results: how sure a projection is (docs/PHASE2_DESIGN.md, section 2.6)."""

from datetime import date
from typing import Self

from pydantic import BaseModel, Field

from app.domain.models import InvestmentRisk
from app.domain.uncertainty import DEFAULT_PATHS, DEFAULT_SEED, BandPoint, GoalDates, Percentiles
from app.schemas.common import cents
from app.schemas.plan import Rates
from app.schemas.scenarios import SimulateRequest
from app.services.uncertainty import Uncertainty


def share(value: float) -> float:
    """A share of futures, 0 to 1, to 4 decimals (1,000 futures need only 3)."""
    return round(value, 4)


class UncertaintyRequest(SimulateRequest):
    paths: int = Field(DEFAULT_PATHS, ge=1, le=10_000, description="Number of simulated futures.")
    seed: int = Field(
        DEFAULT_SEED,
        ge=0,
        le=2**31 - 1,
        description="Fixes the random returns: the same seed always gives the same futures.",
    )


class PercentilesOut(BaseModel):
    p10: float
    p50: float
    p90: float

    @classmethod
    def from_domain(cls, p: Percentiles) -> Self:
        return cls(p10=cents(p.p10), p50=cents(p.p50), p90=cents(p.p90))


class GoalDatesOut(BaseModel):
    """Dates by which 10%, 50% and 90% of futures have first reached the target. Null when
    that share of futures doesn't reach it within the horizon."""

    p10: date | None
    p50: date | None
    p90: date | None

    @classmethod
    def from_domain(cls, d: GoalDates) -> Self:
        return cls(p10=d.p10, p50=d.p50, p90=d.p90)


class ReachedByOut(BaseModel):
    date: date
    share: float = Field(description="Share of futures that have reached the target by then.")


class BandPointOut(BaseModel):
    month: int
    date: date
    p10: float
    p50: float
    p90: float

    @classmethod
    def from_domain(cls, b: BandPoint) -> Self:
        return cls(month=b.month, date=b.date, p10=cents(b.p10), p50=cents(b.p50), p90=cents(b.p90))


class UncertaintyOut(BaseModel):
    scenario_name: str
    assumption_set: str
    assumptions: Rates = Field(description="Effective assumptions, after overrides.")
    investment_risk: InvestmentRisk
    volatility: float = Field(description="Yearly volatility of returns for the risk level.")
    paths: int
    seed: int
    horizon_months: int = Field(description="Target date plus 10 years, at most 50 years.")
    target_amount: float
    target_date: date
    months_to_target_date: int
    probability_by_target_date: float = Field(
        description="Share of futures with cash + investments at or above the target on the "
        "target date."
    )
    probability_margin: float = Field(
        description="Half-width of the 95% interval of that share: 1.96 * sqrt(p(1 - p) / n)."
    )
    goal_dates: GoalDatesOut
    not_reached_share: float = Field(
        description="Share of futures that don't reach the target within the horizon."
    )
    value_at_target_date: PercentilesOut = Field(
        description="Cash + investments on the target date: 10th, 50th and 90th percentile."
    )
    shortfall_when_missed: PercentilesOut | None = Field(
        description="How far below the target the futures that miss it are. Null when none do."
    )
    reached_by: list[ReachedByOut] = Field(
        description="Each 1 January within the horizon, and the target date."
    )
    bands: list[BandPointOut] = Field(
        description="Cash + investments percentiles for every month, from today (month 0)."
    )

    @classmethod
    def from_service(cls, u: Uncertainty) -> Self:
        r = u.result
        shortfall = r.shortfall_when_missed
        return cls(
            scenario_name=u.scenario_name,
            assumption_set=u.assumption_set,
            assumptions=Rates.from_domain(u.assumptions),
            investment_risk=u.investment_risk,
            volatility=r.volatility,
            paths=r.paths,
            seed=r.seed,
            horizon_months=r.horizon_months,
            target_amount=cents(r.target_amount),
            target_date=r.target_date,
            months_to_target_date=r.months_to_target_date,
            probability_by_target_date=share(r.probability_by_target_date),
            probability_margin=share(r.probability_margin),
            goal_dates=GoalDatesOut.from_domain(r.goal_dates),
            not_reached_share=share(r.not_reached_share),
            value_at_target_date=PercentilesOut.from_domain(r.value_at_target_date),
            shortfall_when_missed=(
                None if shortfall is None else PercentilesOut.from_domain(shortfall)
            ),
            reached_by=[ReachedByOut(date=x.date, share=share(x.share)) for x in r.reached_by],
            bands=[BandPointOut.from_domain(b) for b in r.bands],
        )
