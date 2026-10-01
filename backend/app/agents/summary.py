"""'What does this mean for me?' (docs/PHASE3_DESIGN.md, section 3).

Code chooses the facts: short sentences built from the engine's (rounded) results, picked by
rules so only what applies is said. A language model may reword them into a summary, under
the same checks as the chat's replies (every figure copied exactly, no advice); otherwise the
facts themselves, joined, are the summary.
"""

from dataclasses import dataclass

from app.agents.explain import day, eur, goal_sentence, share
from app.schemas.scenarios import ScenarioResultOut
from app.schemas.uncertainty import UncertaintyOut

NINE_IN_TEN = 0.9


@dataclass(frozen=True)
class Summary:
    text: str
    facts: list[str]
    """What the text was written from: the figures it may use."""
    worded_by: str
    """A model's name, or "template" when the facts are shown as they are."""


def projection_facts(r: ScenarioResultOut, f: UncertaintyOut) -> list[str]:
    """The projection page in a few sentences: when the goal is reached, how often on time in
    the simulated futures, what being on time in 9 of 10 would take, and a caution if the plan
    runs short somewhere."""
    facts = [goal_sentence(r)]
    if r.months_to_goal != 0:  # not already covered by today's cash and investments
        facts.append(
            f"In {share(f.probability_by_target_date)} of {f.paths:,} simulated futures, the "
            f"goal is reached by {day(r.target_date)}."
        )
        nine = next((x for x in f.required_monthly_investment if x.share == NINE_IN_TEN), None)
        if nine is not None and nine.monthly_amount is not None:
            if nine.monthly_amount > r.monthly_contribution:
                facts.append(
                    f"To be on time in 9 of 10 futures, about {eur(nine.monthly_amount)} a month "
                    f"would need to be invested; today {eur(r.monthly_contribution)} is invested "
                    "each month."
                )
            else:
                facts.append(
                    f"The {eur(r.monthly_contribution)} invested each month today is at least "
                    f"the {eur(nine.monthly_amount)} that being on time in 9 of 10 futures takes."
                )
        missed = f.shortfall_when_missed
        if missed is not None and f.probability_by_target_date < NINE_IN_TEN:
            facts.append(
                f"In the futures that miss the target date, they are typically {eur(missed.p50)} "
                "short."
            )
    cautions = [w.message for w in r.warnings if w.code != "debt_paid_off"]
    if cautions:
        facts.append(cautions[0])
    return facts


def template_summary(facts: list[str]) -> str:
    return " ".join(facts)
