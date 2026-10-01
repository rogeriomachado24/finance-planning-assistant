"""Application settings, read from environment variables or `backend/.env`."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    database_url: str = f"sqlite:///{(BACKEND_DIR / 'finance.db').as_posix()}"
    """SQLAlchemy URL. Defaults to a SQLite file in `backend/`, whatever the working directory."""

    llm_provider: Literal["mock", "ollama"] = "mock"
    """Who parses chat messages and words the replies. `mock` needs no model."""
    ollama_model: str = "qwen2.5:3b"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_rewrite_replies: bool = False
    """Let the model reword chat replies and page summaries (strictly checked). Off: small
    models misstate facts in ways the checks can't catch (docs/PHASE1_DESIGN.md,
    docs/PHASE3_DESIGN.md 3.3)."""


@lru_cache
def get_settings() -> Settings:
    return Settings()
