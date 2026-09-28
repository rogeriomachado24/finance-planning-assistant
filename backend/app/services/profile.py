from sqlalchemy.orm import Session

from app.db.models import SINGLE_PROFILE_ID, FinancialProfileRecord
from app.domain.cashflow import FinancialPosition, summarize_position
from app.domain.models import FinancialProfile
from app.services.errors import NotFoundError
from app.services.mapping import profile_from_record, write_profile


def get_profile(session: Session) -> FinancialProfile:
    record = session.get(FinancialProfileRecord, SINGLE_PROFILE_ID)
    if record is None:
        raise NotFoundError("no financial profile has been saved yet")
    return profile_from_record(record)


def save_profile(session: Session, profile: FinancialProfile) -> FinancialProfile:
    """Create or replace the single profile. Returns it as stored (money rounded to the cent)."""
    record = session.get(FinancialProfileRecord, SINGLE_PROFILE_ID)
    if record is None:
        record = FinancialProfileRecord(id=SINGLE_PROFILE_ID)
        session.add(record)
    write_profile(record, profile)
    session.commit()
    return profile_from_record(record)


def get_position(session: Session) -> FinancialPosition:
    """Today's surplus, savings rate, liquid assets and net worth."""
    return summarize_position(get_profile(session))
