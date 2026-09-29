from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.api.deps import SessionDep

router = APIRouter(tags=["health"])


class LlmStatus(BaseModel):
    provider: str = Field(description='"mock" (no model) or the model name, e.g. "phi3".')
    available: bool = Field(
        description="Whether the model answers. The chat works either way: without a model, "
        "rules and templates handle every message."
    )


class HealthOut(BaseModel):
    status: str
    database: str
    llm: LlmStatus


@router.get("/health")
def health(session: SessionDep, request: Request) -> HealthOut:
    """Liveness check: the database and the chat's language model."""
    session.execute(text("SELECT 1"))
    provider = request.app.state.chat_provider
    return HealthOut(
        status="ok",
        database="ok",
        llm=LlmStatus(provider=provider.name, available=provider.is_available()),
    )
