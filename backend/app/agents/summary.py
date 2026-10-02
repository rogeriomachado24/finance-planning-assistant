"""'What does this mean for me?' (docs/PHASE3_DESIGN.md, section 3).

Code chooses the facts, each a short label and a short text built from the engine's (rounded)
results, picked by rules so only what applies is said. The page shows them as a labelled list.
A language model may reword them into a paragraph, under the same checks as the chat's
replies (every figure copied exactly, no advice).
"""

from dataclasses import dataclass

from app.agents.explain import (
    day,
    duration,
    eur,
    points_difference,
    relative_timing,
    share,
)
from app.schemas.scenarios import ComparedScenarioOut, ScenarioResultOut
from app.schemas.uncertainty import FuturesComparisonOut, UncertaintyOut

NINE_IN_TEN = 0.9


@dataclass(frozen=True)
class Fact:
    label: str
    """What the line is about, e.g. "Simulated futures"."""
    text: str
    """The fact itself, e.g. "on time in about 93% of 1,000"."""

    @property
    def sentence(self) -> str:
        """The fact as one sentence, for the model and the checks: "Label: text"."""
        return f"{self.label}: {self.text}"


def sentences(facts: list[Fact]) -> list[str]:
    return [f.sentence for f in facts]


def template_summary(facts: list[Fact]) -> str:
    return " ".join(sentences(facts))


def projection_facts(r: ScenarioResultOut, f: UncertaintyOut) -> list[Fact]:
    """The projection page in a few lines: when the goal is reached, how often on time in the
    simulated futures, what being on time in 9 of 10 would take, how far off the misses are,
    and a caution if the plan runs short somewhere."""
    goal = f"Goal ({eur(r.target_amount)} by {day(r.target_date)})"
    if r.months_to_goal == 0:
        return [Fact(goal, "already covered by today's cash and investments.")] + _caution(r)

    if r.reaches_goal and r.projected_goal_date and r.months_to_goal is not None:
        early = r.months_to_target_date - r.months_to_goal
        timing = "on the target date" if early == 0 else f"{duration(early)} early"
        status = f"under these assumptions, reached on {day(r.projected_goal_date)}, {timing}."
    else:
        later = (
            f"reached on {day(r.projected_goal_date)} instead."
            if r.projected_goal_date
            else "not reached within 50 years."
        )
        status = f"under these assumptions, not reached: {eur(r.shortfall)} short; {later}"
    facts = [
        Fact(goal, status),
        Fact(
            "Simulated futures",
            f"on time in {share(f.probability_by_target_date)} of {f.paths:,}.",
        ),
    ]

    nine = next((x for x in f.required_monthly_investment if x.share == NINE_IN_TEN), None)
    if nine is not None and nine.monthly_amount is not None:
        if nine.monthly_amount > r.monthly_contribution:
            facts.append(
                Fact(
                    "To be on time in 9 of 10",
                    f"about {eur(nine.monthly_amount)} a month would need to be invested "
                    f"(today {eur(r.monthly_contribution)}).",
                )
            )
        else:
            facts.append(
                Fact(
                    "On time in 9 of 10",
                    f"the {eur(r.monthly_contribution)} invested each month today is at least "
                    f"the {eur(nine.monthly_amount)} it takes.",
                )
            )
    missed = f.shortfall_when_missed
    if missed is not None and f.probability_by_target_date < NINE_IN_TEN:
        facts.append(Fact("When it's missed", f"typically {eur(missed.p50)} short."))
    return facts + _caution(r)


def _caution(r: ScenarioResultOut) -> list[Fact]:
    cautions = [w.message for w in r.warnings if w.code != "debt_paid_off"]
    return [Fact("Note", cautions[0])] if cautions else []


def compare_facts(
    scenarios: list[ComparedScenarioOut], futures: FuturesComparisonOut | None
) -> list[Fact]:
    """The Compare page in a few lines: the current plan, then each scenario's difference from
    it (goal date and share of futures on time), then which scenario reaches the goal earliest
    and which is on time in the most futures. Stated as differences, never as "the best
    option"."""
    baseline, others = scenarios[0], scenarios[1:]
    on_time = {f.name: f for f in futures.scenarios} if futures else {}
    b = baseline.result
    when = f"on {day(b.projected_goal_date)}" if b.projected_goal_date else "not within 50 years"
    text = f"{eur(b.target_amount)} reached {when}"
    if baseline.name in on_time:
        text += (
            f"; on time ({day(b.target_date)}) in "
            f"{share(on_time[baseline.name].probability_by_target_date)} of "
            f"{futures.paths:,} simulated futures"  # type: ignore[union-attr]
        )
    facts = [Fact(baseline.name, text + ".")]

    for s in others:
        r, delta = s.result, s.vs_baseline
        text = "reached " + (
            f"on {day(r.projected_goal_date)}" if r.projected_goal_date else "not within 50 years"
        )
        if delta.goal_months_earlier is not None:
            text += f" ({relative_timing(delta.goal_months_earlier)})"
        if s.name in on_time:
            f = on_time[s.name]
            text += (
                f"; on time in {share(f.probability_by_target_date)} of futures "
                f"({points_difference(f.points_difference)})"
            )
        facts.append(Fact(s.name, text + "."))

    reached = [s for s in scenarios if s.result.months_to_goal is not None]
    if reached:
        soonest = min(s.result.months_to_goal for s in reached)  # type: ignore[type-var]
        earliest = [s for s in reached if s.result.months_to_goal == soonest]
        e = earliest[0]
        if len(earliest) == 1 and e is not baseline and e.result.projected_goal_date:
            facts.append(Fact("Earliest", f"{e.name}, on {day(e.result.projected_goal_date)}."))
    if on_time:
        top = max(f.probability_by_target_date for f in on_time.values())
        # Compared as displayed: two "more than 99%" are a tie, so no single scenario is named.
        most = [n for n, f in on_time.items() if share(f.probability_by_target_date) == share(top)]
        if len(most) == 1 and most[0] != baseline.name:
            facts.append(Fact("On time most often", f"{most[0]} ({share(top)})."))
        for s in others:
            f = on_time.get(s.name)
            invests_more = s.result.monthly_contribution > b.monthly_contribution
            if f is not None and invests_more and f.probability_difference < 0:
                facts.append(
                    Fact(
                        "Note",
                        f"{s.name} moves money from cash, which is safe in the model, into "
                        "investments, which vary: typical futures end higher, but it is on time "
                        "in fewer futures.",
                    )
                )
                break
    return facts
