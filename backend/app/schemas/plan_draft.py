"""Describe your plan: a description in, a draft of the forms out (nothing is saved)."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.agents.plan_draft import DraftReply, PlanDraft


class DraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None = (
        Field(None, description="What the person wrote. Omit to get the next question only.")
    )
    draft: PlanDraft = Field(
        default_factory=PlanDraft,
        description="The draft so far, as returned last time: the server keeps nothing.",
    )


class DraftOut(DraftReply):
    read_by: str = Field(description='Who read the message: "rules", or a model\'s name.')
