from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.db.migrations import upgrade_to_head
from app.db.session import create_db_engine, create_session_factory
from app.services.assumptions import save_assumption_set
from app.services.goals import create_goal
from app.services.profile import save_profile
from tests.sample_plan import BASE, GOAL, PROFILE, TODAY


@pytest.fixture
def empty_db_url(tmp_path: Path) -> str:
    """A path where no database exists yet (nothing migrated)."""
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


@pytest.fixture
def db_url(empty_db_url: str) -> str:
    """A fresh SQLite database built by the real migrations, not by `metadata.create_all`."""
    upgrade_to_head(empty_db_url)
    return empty_db_url


@pytest.fixture
def engine(db_url: str) -> Iterator[Engine]:
    engine = create_db_engine(db_url)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with create_session_factory(engine)() as session:
        yield session


@pytest.fixture
def plan(session: Session) -> Session:
    """A database holding the sample profile, the base assumption set and an active goal."""
    save_profile(session, PROFILE)
    save_assumption_set(session, "base", BASE)
    create_goal(session, GOAL, TODAY)
    return session
