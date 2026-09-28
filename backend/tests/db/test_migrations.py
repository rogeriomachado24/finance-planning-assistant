from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Engine, inspect

from app.db.base import Base
from app.db.migrations import alembic_config

TABLES = {"financial_profiles", "goals", "assumption_sets", "scenarios"}


def test_upgrade_creates_all_tables(engine: Engine):
    assert set(inspect(engine).get_table_names()) == TABLES | {"alembic_version"}


def test_migrations_match_the_models(engine: Engine):
    """Fails if a model changed without a migration (`alembic revision --autogenerate`)."""
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert diff == []


def test_downgrade_removes_all_tables(engine: Engine, db_url: str):
    command.downgrade(alembic_config(db_url), "base")
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}
