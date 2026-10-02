"""How often a model's page summaries pass the checks, and why they fail when they don't.

    python -m app.agents.evaluate_summaries --model qwen3:4b-instruct [--show]

Each plan runs through the engine (projection and simulated futures, or every scenario for
Compare), the facts are chosen as for the page, and the model rewords them. The same checks
as in the app decide whether its text would be shown (every figure copied exactly, no word
durations, no advice).
"""

import argparse
import sys
import time
from dataclasses import replace
from datetime import date

from app.agents.ollama import SUMMARY_SYSTEM, OllamaProvider, check_explanation
from app.agents.summary import compare_facts, projection_facts, sentences
from app.config import get_settings
from app.domain.models import Assumptions, FinancialProfile, Goal, GoalType
from app.domain.scenarios import (
    Scenario,
    ScenarioOverrides,
    compare_scenarios,
    default_scenarios,
    delta_from_baseline,
    run_scenario,
)
from app.domain.uncertainty import (
    VOLATILITY,
    compare_uncertainty,
    points_difference,
    probability_difference,
    simulate_uncertainty,
)
from app.schemas.scenarios import ComparedScenarioOut, ScenarioResultOut
from app.schemas.uncertainty import FuturesComparisonOut, UncertaintyOut
from app.services.scenarios import ComparedScenario
from app.services.uncertainty import ComparedFutures, FuturesComparison, Uncertainty

START = date(2026, 10, 1)
BASE = Assumptions(annual_return=0.05, annual_salary_growth=0.02, annual_expense_growth=0.02)
PROFILE = FinancialProfile(
    monthly_net_income=2500,
    monthly_expenses=1700,
    cash=10_000,
    investments=15_000,
    monthly_investment_contribution=400,
)
GOAL = Goal("Buy a house", 80_000, date(2032, 6, 1), GoalType.HOUSE)

PLANS: list[tuple[str, FinancialProfile, Goal]] = [
    ("on track", PROFILE, GOAL),
    ("behind target", PROFILE, replace(GOAL, target_amount=120_000)),
    ("already covered", replace(PROFILE, cash=90_000), GOAL),
    ("high risk", replace(PROFILE, investment_risk="high"), GOAL),  # type: ignore[arg-type]
    ("short deadline", PROFILE, replace(GOAL, target_amount=40_000, target_date=date(2028, 4, 1))),
    ("spending more than income", replace(PROFILE, monthly_expenses=2700), GOAL),
    (
        "debt being repaid",
        replace(PROFILE, debt_balance=6000, monthly_debt_payment=300, monthly_expenses=1400),
        GOAL,
    ),
    (
        "long retirement goal",
        replace(PROFILE, monthly_investment_contribution=600),
        Goal("Retirement", 500_000, date(2056, 1, 1), GoalType.RETIREMENT),
    ),
]


def facts_for(profile: FinancialProfile, goal: Goal) -> list[str]:
    plan = Scenario("Current plan")
    result = ScenarioResultOut.from_domain(run_scenario(plan, profile, BASE, goal, START))
    futures = simulate_uncertainty(
        plan, profile, BASE, goal, START, VOLATILITY[profile.investment_risk]
    )
    report = Uncertainty("Current plan", "base", BASE, profile.investment_risk, futures)
    return sentences(projection_facts(result, UncertaintyOut.from_service(report)))


SPEND_LESS = Scenario("Spend €200 less", ScenarioOverrides(monthly_expenses_delta=-200))
COMPARISONS: list[tuple[str, FinancialProfile, Goal]] = [
    ("compare: on track", PROFILE, GOAL),
    ("compare: behind target", PROFILE, replace(GOAL, target_amount=120_000)),
    ("compare: high risk", replace(PROFILE, investment_risk="high"), GOAL),  # type: ignore[arg-type]
]


def compare_facts_for(profile: FinancialProfile, goal: Goal) -> list[str]:
    """The Compare page's facts: the built-in scenarios and one saved what-if."""
    scenarios = [*default_scenarios(BASE), SPEND_LESS]
    results = compare_scenarios(scenarios, profile, BASE, goal, START)
    compared = [
        ComparedScenarioOut.from_domain(
            ComparedScenario(s, r, delta_from_baseline(r, results[0]), None)
        )
        for s, r in zip(scenarios, results, strict=True)
    ]
    futures = compare_uncertainty(
        scenarios, profile, BASE, goal, START, VOLATILITY[profile.investment_risk]
    )
    comparison = FuturesComparison(
        "base",
        profile.investment_risk,
        [
            ComparedFutures(
                s, f, probability_difference(f, futures[0]), points_difference(f, futures[0]), None
            )
            for s, f in zip(scenarios, futures, strict=True)
        ],
    )
    return sentences(compare_facts(compared, FuturesComparisonOut.from_service(comparison)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--model", required=True, help="an Ollama model, e.g. qwen2.5:3b")
    parser.add_argument("--show", action="store_true", help="print every text")
    args = parser.parse_args(argv)

    provider = OllamaProvider(args.model, get_settings().ollama_base_url)
    provider.warm_up()
    passed, seconds = 0, []
    cases = [(n, facts_for(p, g)) for n, p, g in PLANS]
    cases += [(n, compare_facts_for(p, g)) for n, p, g in COMPARISONS]
    for name, case_facts in cases:
        facts = "\n".join(case_facts)
        began = time.perf_counter()
        text = provider._writer.invoke(
            [("system", SUMMARY_SYSTEM), ("human", f"Facts:\n{facts}")]
        ).content.strip()
        seconds.append(time.perf_counter() - began)
        try:
            check_explanation(text, facts)
            passed += 1
            verdict = "passed"
        except Exception as exc:
            verdict = f"rejected: {exc}"
        print(f"- {name}: {verdict}")
        if args.show:
            print(f"    facts: {facts}\n    text:  {text}\n")
    seconds.sort()
    print(
        f"\n{args.model}: {passed}/{len(cases)} summaries passed the checks; "
        f"median {seconds[len(seconds) // 2]:.1f}s"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
