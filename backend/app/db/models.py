"""Database tables. Named `*Record` to keep them distinct from the domain dataclasses.

Constraints mirror the domain validation (non-negative money, rates in (-1, 1]) so the
database never holds a value the engine would reject, whoever writes it.
"""

from datetime import date
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, CheckConstraint, Enum, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Money, Rate, TimestampMixin
from app.domain.models import GoalType, InvestmentRisk

SINGLE_PROFILE_ID = 1


def _non_negative(*columns: str) -> tuple[CheckConstraint, ...]:
    return tuple(CheckConstraint(f"{c} >= 0", name=f"{c}_gte_0") for c in columns)


def _valid_rate(*columns: str) -> tuple[CheckConstraint, ...]:
    return tuple(CheckConstraint(f"{c} > -1 AND {c} <= 1", name=f"{c}_range") for c in columns)


def _string_enum(enum: type[StrEnum], length: int) -> Enum:
    """Stored as its value, e.g. "medium", in a plain string column."""
    return Enum(
        enum,
        native_enum=False,
        length=length,
        values_callable=lambda members: [member.value for member in members],
    )


class FinancialProfileRecord(TimestampMixin, Base):
    """The user's current position. Phase 1 has exactly one profile, always with id 1."""

    __tablename__ = "financial_profiles"
    __table_args__ = (
        CheckConstraint(f"id = {SINGLE_PROFILE_ID}", name="single_profile"),
        CheckConstraint("age BETWEEN 0 AND 120", name="age_range"),
        CheckConstraint(
            "investment_risk IN ({})".format(", ".join(f"'{r.value}'" for r in InvestmentRisk)),
            name="investment_risk_values",
        ),
        *_non_negative(
            "monthly_net_income",
            "other_monthly_income",
            "monthly_expenses",
            "cash",
            "investments",
            "monthly_investment_contribution",
            "debt_balance",
            "monthly_debt_payment",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    age: Mapped[int | None]
    monthly_net_income: Mapped[Money]
    other_monthly_income: Mapped[Money]
    monthly_expenses: Mapped[Money]
    cash: Mapped[Money]
    investments: Mapped[Money]
    monthly_investment_contribution: Mapped[Money]
    debt_balance: Mapped[Money]
    monthly_debt_payment: Mapped[Money]
    investment_risk: Mapped[InvestmentRisk] = mapped_column(
        _string_enum(InvestmentRisk, length=10),
        default=InvestmentRisk.MEDIUM,
        server_default=InvestmentRisk.MEDIUM.value,
    )


class GoalRecord(TimestampMixin, Base):
    """A savings goal. Several may be stored, but at most one is active."""

    __tablename__ = "goals"
    __table_args__ = (
        CheckConstraint("target_amount > 0", name="target_amount_gt_0"),
        # Partial unique index: uniqueness applies only to rows where is_active is true.
        Index(
            "uq_goals_single_active",
            "is_active",
            unique=True,
            sqlite_where=text("is_active = 1"),
            postgresql_where=text("is_active"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    goal_type: Mapped[GoalType] = mapped_column(_string_enum(GoalType, length=30))
    target_amount: Mapped[Money]
    target_date: Mapped[date]
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True)


class AssumptionSetRecord(TimestampMixin, Base):
    """A named set of forward-looking rates, e.g. conservative / base / optimistic."""

    __tablename__ = "assumption_sets"
    __table_args__ = _valid_rate(
        "annual_return", "annual_salary_growth", "annual_expense_growth", "annual_inflation"
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    annual_return: Mapped[Rate]
    annual_salary_growth: Mapped[Rate]
    annual_expense_growth: Mapped[Rate]
    annual_inflation: Mapped[Rate]


class ScenarioRecord(TimestampMixin, Base):
    """A saved scenario definition. Results are never stored; they're always recomputed."""

    __tablename__ = "scenarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    overrides: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    """The `ScenarioOverrides` fields that are set, e.g. {"annual_return": 0.03}."""
