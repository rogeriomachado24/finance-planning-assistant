"""The stored plan: profile, goals and assumption sets."""

from dataclasses import asdict
from datetime import date
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.domain.cashflow import FinancialPosition
from app.domain.models import (
    PROFILE_MONEY_FIELDS,
    Assumptions,
    FinancialProfile,
    Goal,
    GoalType,
    InvestmentRisk,
)
from app.schemas.common import Money, Rate, cents
from app.services.assumptions import SavedAssumptionSet
from app.services.goals import SavedGoal

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class ProfileIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    monthly_net_income: Money = Field(description="Take-home pay; grows with salary growth.")
    monthly_expenses: Money = Field(description="Living expenses, excluding debt payments.")
    cash: Money = 0
    investments: Money = 0
    monthly_investment_contribution: Money = 0
    other_monthly_income: Money = Field(0, description="Income that does not grow.")
    debt_balance: Money = 0
    monthly_debt_payment: Money = 0
    age: int | None = Field(None, ge=0, le=120)
    investment_risk: InvestmentRisk = Field(
        InvestmentRisk.MEDIUM,
        description="How widely yearly investment returns vary: low 5%, medium 10%, high 15% "
        "volatility. Used only by the uncertainty simulation.",
    )

    def to_domain(self) -> FinancialProfile:
        return FinancialProfile(**self.model_dump())


class Profile(BaseModel):
    """Profile values as output. No input limits: a what-if may legitimately exceed them."""

    monthly_net_income: float
    monthly_expenses: float
    cash: float
    investments: float
    monthly_investment_contribution: float
    other_monthly_income: float
    debt_balance: float
    monthly_debt_payment: float
    age: int | None
    investment_risk: InvestmentRisk

    @classmethod
    def from_domain(cls, profile: FinancialProfile) -> Self:
        data = asdict(profile)
        return cls(**{k: cents(v) if k in PROFILE_MONEY_FIELDS else v for k, v in data.items()})


class PositionOut(BaseModel):
    total_monthly_income: float
    monthly_expenses: float
    monthly_debt_payment: float
    monthly_surplus: float
    savings_rate: float | None = Field(description="Surplus / income; null when income is 0.")
    liquid_assets: float = Field(description="Cash + investments.")
    net_worth: float

    @classmethod
    def from_domain(cls, position: FinancialPosition) -> Self:
        rate = position.savings_rate
        data = {k: cents(v) for k, v in asdict(position).items() if k != "savings_rate"}
        return cls(**data, savings_rate=None if rate is None else round(rate, 4))


class ProfileOut(BaseModel):
    profile: Profile
    position: PositionOut = Field(description="Today's figures, computed from the profile.")


class GoalIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    goal_type: GoalType = GoalType.OTHER
    target_amount: Money = Field(gt=0, description="Amount of cash + investments to reach.")
    target_date: date
    description: Annotated[str, StringConstraints(max_length=1000)] | None = None

    def to_domain(self) -> Goal:
        return Goal(**self.model_dump())


class GoalOut(GoalIn):
    id: int
    is_active: bool

    @classmethod
    def from_saved(cls, saved: SavedGoal) -> Self:
        goal = asdict(saved.goal) | {"target_amount": cents(saved.goal.target_amount)}
        return cls(id=saved.id, is_active=saved.is_active, **goal)


class Rates(BaseModel):
    model_config = ConfigDict(extra="forbid")

    annual_return: Rate = 0
    annual_salary_growth: Rate = 0
    annual_expense_growth: Rate = 0
    annual_inflation: Rate = Field(0, description="Displayed only; not used in calculations.")

    def to_domain(self) -> Assumptions:
        return Assumptions(**self.model_dump())

    @classmethod
    def from_domain(cls, assumptions: Assumptions) -> Self:
        return cls(**asdict(assumptions))


class PlanStatusOut(BaseModel):
    has_profile: bool = Field(description="Your finances have been saved.")
    has_goal: bool = Field(description="An active goal exists.")
    ready: bool = Field(description="Projections, comparisons and the chat can run.")


class AssumptionSetOut(BaseModel):
    name: str
    assumptions: Rates

    @classmethod
    def from_saved(cls, saved: SavedAssumptionSet) -> Self:
        return cls(name=saved.name, assumptions=Rates.from_domain(saved.assumptions))
