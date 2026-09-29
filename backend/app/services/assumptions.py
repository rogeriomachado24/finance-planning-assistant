from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AssumptionSetRecord
from app.domain.errors import InvalidInputError
from app.domain.models import Assumptions
from app.services.errors import NotFoundError
from app.services.mapping import assumptions_from_record, write_assumptions

DEFAULT_ASSUMPTION_SET = "base"

ASSUMPTION_PRESETS = {
    "conservative": Assumptions(
        annual_return=0.02,
        annual_salary_growth=0.01,
        annual_expense_growth=0.03,
        annual_inflation=0.03,
    ),
    "base": Assumptions(
        annual_return=0.05,
        annual_salary_growth=0.02,
        annual_expense_growth=0.02,
        annual_inflation=0.02,
    ),
    "optimistic": Assumptions(
        annual_return=0.07,
        annual_salary_growth=0.03,
        annual_expense_growth=0.02,
        annual_inflation=0.02,
    ),
}
"""Illustrative starting values that the user can edit. Not forecasts."""


@dataclass(frozen=True)
class SavedAssumptionSet:
    id: int
    name: str
    assumptions: Assumptions


def _saved(record: AssumptionSetRecord) -> SavedAssumptionSet:
    return SavedAssumptionSet(
        id=record.id, name=record.name, assumptions=assumptions_from_record(record)
    )


def list_assumption_sets(session: Session) -> list[SavedAssumptionSet]:
    records = session.scalars(select(AssumptionSetRecord).order_by(AssumptionSetRecord.id))
    return [_saved(r) for r in records]


def get_assumption_set(session: Session, name: str = DEFAULT_ASSUMPTION_SET) -> SavedAssumptionSet:
    record = session.scalar(select(AssumptionSetRecord).where(AssumptionSetRecord.name == name))
    if record is None:
        raise NotFoundError(f"no assumption set named {name!r}")
    return _saved(record)


def ensure_assumption_presets(session: Session) -> list[str]:
    """Add any preset that isn't stored yet; never overwrite one. Returns the names added."""
    existing = set(session.scalars(select(AssumptionSetRecord.name)))
    added = [name for name in ASSUMPTION_PRESETS if name not in existing]
    for name in added:
        record = AssumptionSetRecord(name=name)
        write_assumptions(record, ASSUMPTION_PRESETS[name])
        session.add(record)
    session.commit()
    return added


def save_assumption_set(
    session: Session, name: str, assumptions: Assumptions
) -> SavedAssumptionSet:
    """Create or replace the assumption set with this name."""
    name = name.strip()
    if not name:
        raise InvalidInputError("assumption set name must not be empty")
    record = session.scalar(select(AssumptionSetRecord).where(AssumptionSetRecord.name == name))
    if record is None:
        record = AssumptionSetRecord(name=name)
        session.add(record)
    write_assumptions(record, assumptions)
    session.commit()
    return _saved(record)
