from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AssumptionSetRecord
from app.domain.errors import InvalidInputError
from app.domain.models import Assumptions
from app.services.errors import NotFoundError
from app.services.mapping import assumptions_from_record, write_assumptions

DEFAULT_ASSUMPTION_SET = "base"


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
