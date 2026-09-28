from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.api.deps import SessionDep

router = APIRouter(tags=["health"])


class HealthOut(BaseModel):
    status: str
    database: str


@router.get("/health")
def health(session: SessionDep) -> HealthOut:
    """Liveness check. LLM provider status is added with the chat."""
    session.execute(text("SELECT 1"))
    return HealthOut(status="ok", database="ok")
