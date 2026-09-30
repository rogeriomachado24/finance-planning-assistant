"""What-if overrides, scenario definitions and projection results."""

from dataclasses import asdict
from datetime import date
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.domain.goals import GoalProgress
from app.domain.projection import MonthSnapshot, ProjectionWarning, WarningCode
from app.domain.scenarios import Scenario, ScenarioDelta, ScenarioOverrides, ScenarioResult
from app.schemas.common import MAX_MONEY, Money, Rate, cents
from app.schemas.plan import Name, Profile, Rates
from app.services.assumptions import DEFAULT_ASSUMPTION_SET
from app.services.scenarios import ComparedScenario, SavedScenario

Delta = Annotated[float, Field(ge=-MAX_MONEY, le=MAX_MONEY, allow_inf_nan=False)]
"""A change to a monthly amount: positive or negative EUR."""


class OverridesIn(BaseModel):
    """Changes relative to the saved plan. Omitted fields keep their saved value."""

    model_config = ConfigDict(extra="forbid")

    monthly_investment_contribution: Money | None = Field(
        None, description="New monthly contribution. Can't be combined with the delta."
    )
    monthly_investment_contribution_delta: Delta | None = Field(
        None, description="Change to the saved monthly contribution, e.g. 200 or -100."
    )
    monthly_net_income: Money | None = None
    monthly_net_income_delta: Delta | None = Field(
        None, description="Change to monthly take-home pay, e.g. 300 or -200."
    )
    monthly_expenses: Money | None = None
    monthly_expenses_delta: Delta | None = Field(
        None, description="Change to monthly expenses, e.g. -200 to spend 200 less."
    )
    annual_return: Rate | None = None
    annual_salary_growth: Rate | None = None
    annual_expense_growth: Rate | None = None
    first_year_return: Rate | None = Field(
        None, description="Return of the first year only, e.g. -0.3 for a 30% market drop."
    )

    def to_domain(self) -> ScenarioOverrides:
        return ScenarioOverrides(**self.model_dump())

    @classmethod
    def from_domain(cls, overrides: ScenarioOverrides) -> Self:
        return cls(**asdict(overrides))


class ScenarioIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    description: Annotated[str, StringConstraints(max_length=1000)] = ""
    overrides: OverridesIn = OverridesIn()

    def to_domain(self) -> Scenario:
        return Scenario(self.name, self.overrides.to_domain(), self.description)


class SavedScenarioOut(ScenarioIn):
    id: int

    @classmethod
    def from_saved(cls, saved: SavedScenario) -> Self:
        s = saved.scenario
        overrides = OverridesIn.from_domain(s.overrides)
        return cls(id=saved.id, name=s.name, description=s.description, overrides=overrides)


class SimulateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assumption_set: str = DEFAULT_ASSUMPTION_SET
    overrides: OverridesIn = OverridesIn()
    name: Name | None = Field(
        None, description='Defaults to "Current plan", or "What-if" when overrides are set.'
    )


class CompareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assumption_set: str = DEFAULT_ASSUMPTION_SET
    scenarios: list[ScenarioIn] | None = Field(
        None,
        min_length=1,
        max_length=10,
        description="Scenarios to run; the first is the baseline. Omit to run the built-in "
        "scenarios (current plan first), then the saved ones.",
    )


class GoalProgressOut(BaseModel):
    current_amount: float = Field(description="Cash + investments today.")
    remaining: float = Field(description="Still to go; 0 once the target is covered.")
    fraction: float = Field(description="Share of the target already there, from 0 to 1.")

    @classmethod
    def from_domain(cls, progress: GoalProgress) -> Self:
        return cls(
            current_amount=cents(progress.current_amount),
            remaining=cents(progress.remaining),
            fraction=round(progress.fraction, 4),
        )


class WarningOut(BaseModel):
    code: WarningCode
    month: int = Field(description="First month in which the condition occurs.")
    date: date
    message: str

    @classmethod
    def from_domain(cls, warning: ProjectionWarning) -> Self:
        return cls(
            code=warning.code, month=warning.month, date=warning.date, message=warning.message
        )


class SnapshotOut(BaseModel):
    """Balances at the end of the month, and the flows during it."""

    month: int
    date: date
    income: float
    expenses: float
    debt_payment: float
    surplus: float
    contribution: float
    withdrawal: float
    cash: float
    investments: float
    debt: float
    liquid_assets: float
    net_worth: float

    @classmethod
    def from_domain(cls, s: MonthSnapshot) -> Self:
        money = asdict(s) | {"liquid_assets": s.liquid_assets, "net_worth": s.net_worth}
        return cls(**{k: v if k in ("month", "date") else cents(v) for k, v in money.items()})


class ScenarioResultOut(BaseModel):
    scenario_name: str
    profile: Profile = Field(description="Effective profile, after overrides.")
    assumptions: Rates = Field(description="Effective assumptions, after overrides.")
    monthly_contribution: float
    monthly_surplus: float = Field(description="Surplus in the first projected month.")
    target_amount: float
    target_date: date
    months_to_target_date: int
    projected_goal_date: date | None = Field(description="Null when not reached within 50 years.")
    months_to_goal: int | None
    projected_value_at_target_date: float
    reaches_goal: bool
    shortfall: float
    required_monthly_contribution: float | None = Field(
        description="Monthly amount that reaches the target on the target date at the assumed "
        "return. Null when the target date has arrived and the goal isn't reached."
    )
    goal_progress: GoalProgressOut
    warnings: list[WarningOut]
    snapshots: list[SnapshotOut] = Field(description="Monthly series, from today (month 0).")

    @classmethod
    def from_domain(cls, r: ScenarioResult) -> Self:
        required = r.required_monthly_contribution
        return cls(
            scenario_name=r.scenario_name,
            profile=Profile.from_domain(r.profile),
            assumptions=Rates.from_domain(r.assumptions),
            monthly_contribution=cents(r.monthly_contribution),
            monthly_surplus=cents(r.monthly_surplus),
            target_amount=cents(r.target_amount),
            target_date=r.target_date,
            months_to_target_date=r.months_to_target_date,
            projected_goal_date=r.projected_goal_date,
            months_to_goal=r.months_to_goal,
            projected_value_at_target_date=cents(r.projected_value_at_target_date),
            reaches_goal=r.reaches_goal,
            shortfall=cents(r.shortfall),
            required_monthly_contribution=None if required is None else cents(required),
            goal_progress=GoalProgressOut.from_domain(r.goal_progress),
            warnings=[WarningOut.from_domain(w) for w in r.warnings],
            snapshots=[SnapshotOut.from_domain(s) for s in r.snapshots],
        )


class DeltaOut(BaseModel):
    """How a scenario differs from the baseline (the first scenario compared)."""

    goal_months_earlier: int | None = Field(
        description="Months earlier (positive) or later (negative) that the goal is reached. "
        "Null when either scenario doesn't reach it within 50 years."
    )
    value_at_target_difference: float = Field(
        description="Cash + investments on the target date, minus the baseline's."
    )

    @classmethod
    def from_domain(cls, delta: ScenarioDelta) -> Self:
        return cls(
            goal_months_earlier=delta.goal_months_earlier,
            value_at_target_difference=cents(delta.value_at_target_difference),
        )


class ComparedScenarioOut(BaseModel):
    name: str
    description: str
    saved_id: int | None = Field(description="Id of a saved scenario; null for built-in ones.")
    result: ScenarioResultOut
    vs_baseline: DeltaOut

    @classmethod
    def from_domain(cls, compared: ComparedScenario) -> Self:
        return cls(
            name=compared.scenario.name,
            description=compared.scenario.description,
            saved_id=compared.saved_id,
            result=ScenarioResultOut.from_domain(compared.result),
            vs_baseline=DeltaOut.from_domain(compared.vs_baseline),
        )


class CompareOut(BaseModel):
    assumption_set: str
    baseline: str = Field(description="Name of the scenario the differences are measured from.")
    scenarios: list[ComparedScenarioOut]
