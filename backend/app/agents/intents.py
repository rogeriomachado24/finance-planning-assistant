"""What a chat message can ask for. Exactly one of these is produced per message, by the
mock parser or the language model, and then executed by deterministic code.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter

from app.schemas.scenarios import OverridesIn


class _Intent(BaseModel):
    assumption_set: Literal["conservative", "base", "optimistic"] | None = Field(
        None, description="Only when the user names one; otherwise the default set is used."
    )


class RunProjection(_Intent):
    """'Am I on track?', 'show my projection'."""

    kind: Literal["run_projection"] = "run_projection"


class GoalDate(_Intent):
    """'When will I reach my goal?'"""

    kind: Literal["goal_date"] = "goal_date"


class RequiredContribution(_Intent):
    """'How much do I need to invest each month to get there on time?'"""

    kind: Literal["required_contribution"] = "required_contribution"


class WhatIf(_Intent):
    """'What if I invest €200 more per month?' The plan itself is never changed."""

    kind: Literal["what_if"] = "what_if"
    overrides: OverridesIn


class CompareScenarios(_Intent):
    """'Compare my options', 'show the scenarios'."""

    kind: Literal["compare_scenarios"] = "compare_scenarios"


class ExplainAssumptions(_Intent):
    """'What are you assuming?'"""

    kind: Literal["explain_assumptions"] = "explain_assumptions"


class NeedsClarification(BaseModel):
    """Understood partly, but something is missing, e.g. an amount without what it applies to."""

    kind: Literal["needs_clarification"] = "needs_clarification"
    question: str


class Unsupported(BaseModel):
    """Advice requests and anything outside the simulator's scope."""

    kind: Literal["unsupported"] = "unsupported"
    reason: Literal["advice", "out_of_scope", "not_understood"]


Intent = Annotated[
    RunProjection
    | GoalDate
    | RequiredContribution
    | WhatIf
    | CompareScenarios
    | ExplainAssumptions
    | NeedsClarification
    | Unsupported,
    Field(discriminator="kind"),
]

IntentAdapter: TypeAdapter[Intent] = TypeAdapter(Intent)

ANSWERABLE = (
    RunProjection,
    GoalDate,
    RequiredContribution,
    WhatIf,
    CompareScenarios,
    ExplainAssumptions,
)
