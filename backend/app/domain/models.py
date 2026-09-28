"""Core financial inputs. Plain frozen dataclasses so the domain stays framework-free."""

from dataclasses import dataclass, fields
from datetime import date
from enum import StrEnum

from app.domain.errors import InvalidInputError
from app.domain.rates import validate_annual_rate


def _require_non_negative(obj: object, *names: str) -> None:
    for name in names:
        value = getattr(obj, name)
        if value < 0:
            raise InvalidInputError(f"{name} must be >= 0; got {value}")


@dataclass(frozen=True)
class FinancialProfile:
    """The user's current position. Facts about today, not forecasts."""

    monthly_net_income: float
    monthly_expenses: float
    """Living expenses, excluding debt payments."""
    cash: float = 0.0
    investments: float = 0.0
    monthly_investment_contribution: float = 0.0
    other_monthly_income: float = 0.0
    debt_balance: float = 0.0
    monthly_debt_payment: float = 0.0
    age: int | None = None

    def __post_init__(self) -> None:
        _require_non_negative(self, *(f.name for f in fields(self) if f.name != "age"))
        if self.age is not None and not 0 <= self.age <= 120:
            raise InvalidInputError(f"age must be between 0 and 120; got {self.age}")

    @property
    def total_monthly_income(self) -> float:
        return self.monthly_net_income + self.other_monthly_income

    @property
    def liquid_assets(self) -> float:
        return self.cash + self.investments


@dataclass(frozen=True)
class Assumptions:
    """Forward-looking rates, as decimals (0.05 = 5% per year)."""

    annual_return: float = 0.0
    annual_salary_growth: float = 0.0
    annual_expense_growth: float = 0.0
    annual_inflation: float = 0.0
    """Stored and displayed; not used in Phase 1 calculations."""

    def __post_init__(self) -> None:
        for f in fields(self):
            validate_annual_rate(getattr(self, f.name), f.name)


class GoalType(StrEnum):
    HOUSE = "house"
    EMERGENCY_FUND = "emergency_fund"
    RETIREMENT = "retirement"
    EDUCATION = "education"
    VEHICLE = "vehicle"
    TRAVEL = "travel"
    OTHER = "other"


@dataclass(frozen=True)
class Goal:
    """An amount to accumulate by a date. Measured against liquid assets (cash + investments)."""

    name: str
    target_amount: float
    target_date: date
    goal_type: GoalType = GoalType.OTHER
    description: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise InvalidInputError("goal name must not be empty")
        if self.target_amount <= 0:
            raise InvalidInputError(f"target_amount must be > 0; got {self.target_amount}")
