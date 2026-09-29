"""FastAPI application. Run with: uvicorn app.main:app --reload (from backend/)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.agents.graph import build_chat_graph
from app.agents.providers import build_provider
from app.api import chat, health, plan, scenarios
from app.api.errors import register_error_handlers
from app.config import Settings, get_settings
from app.db.session import create_db_engine, create_session_factory
from app.services.setup import prepare_database

DESCRIPTION = """
Financial goal simulator. All figures come from a deterministic, tested engine.

**Projections, not advice:** results depend entirely on the assumptions shown with them
and are not guarantees. Amounts are EUR, rates are decimals (`0.05` = 5%).
"""


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    engine = create_db_engine(settings.database_url)
    session_factory = create_session_factory(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        prepare_database(settings.database_url, session_factory)  # migrations + presets
        yield
        engine.dispose()

    app = FastAPI(
        title="Personal Finance Planning Assistant",
        version="0.1.0",
        description=DESCRIPTION,
        lifespan=lifespan,
    )
    app.state.session_factory = session_factory
    app.state.chat_provider = build_provider(settings)
    app.state.chat_graph = build_chat_graph(session_factory, app.state.chat_provider)
    register_error_handlers(app)
    for module in (health, plan, scenarios, chat):
        app.include_router(module.router)
    return app


app = create_app()
