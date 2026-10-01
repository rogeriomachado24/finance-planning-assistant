"""How often a model's page summary passes the checks, and why it fails when it doesn't.

    python -m app.agents.evaluate_summaries --model qwen2.5:3b [--show]

Each plan runs through the engine (projection and simulated futures), the facts are chosen
as for the Projection page, and the model rewords them. The same checks as in the app decide
whether its text would be shown (every figure copied exactly, no word durations, no advice).
"""

import argparse
import sys
import time
from dataclasses import replace
from datetime import date

from app.agents.ollama import SUMMARY_SYSTEM, OllamaProvider, check_explanation
from app.agents.summary import projection_facts
from app.config import get_settings
from app.domain.models import Assumptions, FinancialProfile, Goal, GoalType
from app.domain.scenarios import Scenario, run_scenario
from app.domain.uncertainty import VOLATILITY, simulate_uncertainty
from app.schemas.scenarios import ScenarioResultOut
from app.schemas.uncertainty import UncertaintyOut
from app.services.uncertainty import Uncertainty

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
    return projection_facts(result, UncertaintyOut.from_service(report))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--model", required=True, help="an Ollama model, e.g. qwen2.5:3b")
    parser.add_argument("--show", action="store_true", help="print every text")
    args = parser.parse_args(argv)

    provider = OllamaProvider(args.model, get_settings().ollama_base_url)
    provider.warm_up()
    passed, seconds = 0, []
    for name, profile, goal in PLANS:
        facts = "\n".join(facts_for(profile, goal))
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
        f"\n{args.model}: {passed}/{len(PLANS)} summaries passed the checks; "
        f"median {seconds[len(seconds) // 2]:.1f}s"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
