from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.agents.intents import Intent
from app.schemas.plan import Rates
from app.schemas.scenarios import ComparedScenarioOut
from app.schemas.uncertainty import FuturesComparisonOut
from app.services.assumptions import DEFAULT_ASSUMPTION_SET


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    thread_id: Annotated[str, StringConstraints(max_length=64)] | None = Field(
        None, description="Continue a conversation. Omit to start a new one."
    )
    assumption_set: str = Field(
        DEFAULT_ASSUMPTION_SET, description="Used unless the message names another set."
    )


class ChatResponse(BaseModel):
    thread_id: str
    reply: str = Field(description="Commentary. The figures to display are in `results`.")
    status: Literal["answered", "clarification", "declined"]
    intent: Intent = Field(description="How the message was understood (structured).")
    assumption_set: str | None
    assumptions: Rates | None = Field(description="The rates behind `results`.")
    results: list[ComparedScenarioOut] = Field(
        description="The engine's results; the first is the current plan (the baseline)."
    )
    futures: FuturesComparisonOut | None = Field(
        description="For likelihood questions: the same scenarios over simulated futures."
    )
    provider: str
    parsed_by: str = Field(description='Who understood the message: a model name, or "rules".')
    worded_by: str = Field(description='Who wrote the reply: a model name, or "template".')
