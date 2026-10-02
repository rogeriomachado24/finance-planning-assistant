"""'What does this mean for me?': a plain-language summary of a page, with its facts."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field

from app.agents.summary import Fact, sentences
from app.services.assumptions import DEFAULT_ASSUMPTION_SET


class ExplainRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assumption_set: str = DEFAULT_ASSUMPTION_SET


class PointOut(BaseModel):
    label: str = Field(description='What the line is about, e.g. "Simulated futures".')
    text: str = Field(description='The fact, e.g. "on time in about 93% of 1,000."')


class SummaryOut(BaseModel):
    points: list[PointOut] = Field(
        description="The facts chosen by code from the engine's results, as a labelled list: "
        "what the page shows."
    )
    facts: list[str] = Field(description='The same facts as sentences ("Label: text").')
    summary: str = Field(
        description="A paragraph: the model's rewording (checked), or the facts joined."
    )
    worded_by: str = Field(
        description='The model that reworded the facts (checked), or "template" for the facts '
        "as they are."
    )

    @classmethod
    def build(cls, facts: list[Fact], summary: str, worded_by: str) -> Self:
        return cls(
            points=[PointOut(label=f.label, text=f.text) for f in facts],
            facts=sentences(facts),
            summary=summary,
            worded_by=worded_by,
        )
