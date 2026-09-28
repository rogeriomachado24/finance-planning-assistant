"""Run Alembic migrations from Python (tests, app startup, seed script)."""

from alembic import command
from alembic.config import Config

from app.config import BACKEND_DIR


def alembic_config(url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    config.attributes["configure_logger"] = False
    return config


def upgrade_to_head(url: str) -> None:
    command.upgrade(alembic_config(url), "head")
