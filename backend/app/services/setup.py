from sqlalchemy.orm import Session, sessionmaker

from app.db.migrations import upgrade_to_head
from app.services.assumptions import ensure_assumption_presets


def prepare_database(url: str, session_factory: sessionmaker[Session]) -> None:
    """Bring the schema up to date and add any missing assumption presets.

    Safe to run on every start: migrations already applied and presets already stored
    (including ones the user edited) are left alone.
    """
    upgrade_to_head(url)
    with session_factory() as session:
        ensure_assumption_presets(session)
