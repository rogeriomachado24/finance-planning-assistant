"""Conversions between database records (Decimal) and domain objects (float).

Money is stored to the cent and rates to 6 decimal places, rounding half up. Reading a
record builds a domain object, which re-runs the domain validation.
"""

from dataclasses import asdict, fields
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.db.models import AssumptionSetRecord, FinancialProfileRecord, GoalRecord
from app.domain.errors import InvalidInputError
from app.domain.models import Assumptions, FinancialProfile, Goal
from app.domain.scenarios import ScenarioOverrides

CENT = Decimal("0.01")
RATE_PRECISION = Decimal("0.000001")

PROFILE_MONEY_FIELDS = tuple(f.name for f in fields(FinancialProfile) if f.name != "age")
RATE_FIELDS = tuple(f.name for f in fields(Assumptions))


def to_money(value: float) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def to_rate(value: float) -> Decimal:
    return Decimal(str(value)).quantize(RATE_PRECISION, rounding=ROUND_HALF_UP)


def profile_from_record(record: FinancialProfileRecord) -> FinancialProfile:
    money = {name: float(getattr(record, name)) for name in PROFILE_MONEY_FIELDS}
    return FinancialProfile(age=record.age, **money)


def write_profile(record: FinancialProfileRecord, profile: FinancialProfile) -> None:
    record.age = profile.age
    for name in PROFILE_MONEY_FIELDS:
        setattr(record, name, to_money(getattr(profile, name)))


def assumptions_from_record(record: AssumptionSetRecord) -> Assumptions:
    return Assumptions(**{name: float(getattr(record, name)) for name in RATE_FIELDS})


def write_assumptions(record: AssumptionSetRecord, assumptions: Assumptions) -> None:
    for name in RATE_FIELDS:
        setattr(record, name, to_rate(getattr(assumptions, name)))


def goal_from_record(record: GoalRecord) -> Goal:
    return Goal(
        name=record.name,
        target_amount=float(record.target_amount),
        target_date=record.target_date,
        goal_type=record.goal_type,
        description=record.description,
    )


def goal_to_record(goal: Goal) -> GoalRecord:
    return GoalRecord(
        name=goal.name,
        target_amount=to_money(goal.target_amount),
        target_date=goal.target_date,
        goal_type=goal.goal_type,
        description=goal.description,
    )


def overrides_to_dict(overrides: ScenarioOverrides) -> dict[str, float]:
    """Only the fields that are set, e.g. {"monthly_investment_contribution_delta": 100}."""
    return {name: value for name, value in asdict(overrides).items() if value is not None}


def overrides_from_dict(data: dict[str, Any]) -> ScenarioOverrides:
    known = {f.name for f in fields(ScenarioOverrides)}
    unknown = sorted(set(data) - known)
    if unknown:
        raise InvalidInputError(f"unknown scenario overrides: {', '.join(unknown)}")
    return ScenarioOverrides(**data)
