"""'What does this mean for me?' (docs/PHASE3_DESIGN.md, section 3).

Code chooses the facts: short sentences built from the engine's (rounded) results, picked by
rules so only what applies is said. A language model may reword them into a summary, under
the same checks as the chat's replies (every figure copied exactly, no advice); otherwise the
facts themselves, joined, are the summary.
"""

from dataclasses import dataclass

from app.agents.explain import (
    day,
    eur,
    goal_sentence,
    points_difference,
    relative_timing,
    share,
)
from app.schemas.scenarios import ComparedScenarioOut, ScenarioResultOut
from app.schemas.uncertainty import FuturesComparisonOut, UncertaintyOut

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


def compare_facts(
    scenarios: list[ComparedScenarioOut], futures: FuturesComparisonOut | None
) -> list[str]:
    """The Compare page in a few sentences: the current plan, then each scenario's difference
    from it (goal date and share of futures on time), then which scenario reaches the goal
    earliest and which is on time in the most futures. Stated as differences, never as "the
    best option"."""
    baseline, others = scenarios[0], scenarios[1:]
    on_time = {f.name: f for f in futures.scenarios} if futures else {}
    b = baseline.result
    goal, target_day = eur(b.target_amount), day(b.target_date)
    when = f"on {day(b.projected_goal_date)}" if b.projected_goal_date else "not within 50 years"
    first = f"With the {baseline.name.lower()}, the {goal} goal is reached {when}"
    if baseline.name in on_time:
        first += (
            f"; in {share(on_time[baseline.name].probability_by_target_date)} of "
            f"{futures.paths:,} simulated futures it is reached by {target_day}"  # type: ignore[union-attr]
        )
    facts = [first + "."]

    for s in others:
        r, delta = s.result, s.vs_baseline
        line = f"{s.name}: the goal is reached " + (
            f"on {day(r.projected_goal_date)}" if r.projected_goal_date else "not within 50 years"
        )
        if delta.goal_months_earlier is not None:
            line += f" ({relative_timing(delta.goal_months_earlier)})"
        if s.name in on_time:
            f = on_time[s.name]
            line += (
                f", and on time in {share(f.probability_by_target_date)} of futures "
                f"({points_difference(f.points_difference)} than the {baseline.name.lower()})"
            )
        facts.append(line + ".")

    reached = [s for s in scenarios if s.result.months_to_goal is not None]
    if reached:
        soonest = min(s.result.months_to_goal for s in reached)  # type: ignore[type-var]
        earliest = [s for s in reached if s.result.months_to_goal == soonest]
        if (
            len(earliest) == 1
            and earliest[0] is not baseline
            and earliest[0].result.projected_goal_date
        ):
            e = earliest[0]
            facts.append(
                f"{e.name} reaches the goal earliest, on {day(e.result.projected_goal_date)}."
            )
    if on_time:
        top = max(f.probability_by_target_date for f in on_time.values())
        # Compared as displayed: two "more than 99%" are a tie, so no single scenario is named.
        most = [n for n, f in on_time.items() if share(f.probability_by_target_date) == share(top)]
        if len(most) == 1 and most[0] != baseline.name:
            facts.append(f"{most[0]} is on time in the most simulated futures ({share(top)}).")
        for s in others:
            f = on_time.get(s.name)
            invests_more = s.result.monthly_contribution > b.monthly_contribution
            if f is not None and invests_more and f.probability_difference < 0:
                facts.append(
                    f"{s.name} moves money from cash, which is safe in the model, into "
                    "investments, which vary: typical futures end higher, but it is on time in "
                    "fewer futures."
                )
                break
    return facts


def template_summary(facts: list[str]) -> str:
    return " ".join(facts)
