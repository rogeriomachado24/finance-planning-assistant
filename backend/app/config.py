"""Application settings, read from environment variables or `backend/.env`."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    database_url: str = f"sqlite:///{(BACKEND_DIR / 'finance.db').as_posix()}"
    """SQLAlchemy URL. Defaults to a SQLite file in `backend/`, whatever the working directory."""


@lru_cache
def get_settings() -> Settings:
    return Settings()
