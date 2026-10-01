"""'What does this mean for me?': a plain-language summary of a page, with its facts."""

from pydantic import BaseModel, ConfigDict, Field

from app.services.assumptions import DEFAULT_ASSUMPTION_SET


class ExplainRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assumption_set: str = DEFAULT_ASSUMPTION_SET


class SummaryOut(BaseModel):
    summary: str = Field(description="Three to five sentences about the page.")
    facts: list[str] = Field(
        description="What the summary was written from, chosen by code from the engine's results."
    )
    worded_by: str = Field(
        description='The model that reworded the facts (checked), or "template" for the facts '
        "as they are."
    )
