"""Labelled plan descriptions for evaluating "describe your plan" (`python -m
app.agents.evaluate_setup`).

Each case: a first message and the draft it should give (only the fields listed; every other
scored field must stay empty). Written before running any extractor on them, with phrasings
on purpose outside the rules' patterns, so the comparison shows where a model helps. Don't
tune the rules to these cases: it would make the evaluation meaningless.
Dates assume today is 15 Oct 2026.
"""

from typing import NamedTuple


class SetupCase(NamedTuple):
    message: str
    expected: dict


SCORED = (
    "monthly_net_income",
    "other_monthly_income",
    "monthly_expenses",
    "cash",
    "investments",
    "monthly_investment_contribution",
    "debt_balance",
    "monthly_debt_payment",
    "age",
    "goal_target_amount",
    "pending_goal_amount",
    "goal_target_date",
    "goal_type",
)

CASES: list[SetupCase] = [
    SetupCase(
        "I take home about 2,400 a month, spend 1,600, have 8k saved and 5k in an ETF. "
        "I want 60k for a house deposit by June 2032.",
        {
            "monthly_net_income": 2400,
            "monthly_expenses": 1600,
            "cash": 8000,
            "investments": 5000,
            "goal_target_amount": 60000,
            "goal_target_date": "2032-06-01",
            "goal_type": "house",
        },
    ),
    SetupCase(
        "Net salary 3,100 per month. Monthly costs around 2,000. Goal: 20k emergency fund by "
        "the end of 2027.",
        {
            "monthly_net_income": 3100,
            "monthly_expenses": 2000,
            "goal_target_amount": 20000,
            "goal_target_date": "2027-12-01",
            "goal_type": "emergency_fund",
        },
    ),
    SetupCase("I make 45k a year before tax", {}),  # gross pay is not take-home pay
    SetupCase(
        "Rent 850, groceries 300, other stuff maybe 400 a month. I earn 2,700 net.",
        {"monthly_expenses": 1550, "monthly_net_income": 2700},
    ),
    SetupCase(
        "My partner and I want to buy a place in about 5 years, we'd need 50k. I bring home "
        "2,200 monthly.",
        {
            "goal_target_amount": 50000,
            "goal_target_date": "2031-10-01",
            "goal_type": "house",
            "monthly_net_income": 2200,
        },
    ),
    SetupCase(
        "Saving for a wedding in June 2028, need 15000",
        {"goal_target_amount": 15000, "goal_target_date": "2028-06-01", "goal_type": "other"},
    ),
    SetupCase(
        "I've got 12k in a savings account and about 3k in crypto",
        {"cash": 12000, "investments": 3000},
    ),
    SetupCase(
        "I put 250 into my pension fund every month", {"monthly_investment_contribution": 250}
    ),
    SetupCase(
        "I owe 6,500 on my credit card and pay 300 a month",
        {"debt_balance": 6500, "monthly_debt_payment": 300},
    ),
    SetupCase(
        "Student loan of 18k, paying it off at 150/month",
        {"debt_balance": 18000, "monthly_debt_payment": 150},
    ),
    SetupCase(
        "I'm 34, earn 2,900 after tax, spend about 2,100",
        {"age": 34, "monthly_net_income": 2900, "monthly_expenses": 2100},
    ),
    SetupCase(
        "I want to retire with 300k in 25 years",
        {
            "goal_target_amount": 300000,
            "goal_target_date": "2051-10-01",
            "goal_type": "retirement",
        },
    ),
    SetupCase(
        "Trip to Japan next year, budget 5k", {"goal_target_amount": 5000, "goal_type": "travel"}
    ),
    SetupCase(
        "I'd like a 20% deposit on a 300k flat in 6 years",
        {"pending_goal_amount": 60000, "goal_target_date": "2032-10-01", "goal_type": "house"},
    ),
    SetupCase(
        "Take-home is €3.200 and fixed costs are €1.400 plus around €500 for food and fun",
        {"monthly_net_income": 3200, "monthly_expenses": 1900},
    ),
    SetupCase(
        "No debt, no investments, 4k in the bank",
        {"debt_balance": 0, "investments": 0, "cash": 4000},
    ),
    SetupCase(
        "I don't invest yet but I'd like to start with 200 a month",
        {"monthly_investment_contribution": 0},
    ),
    SetupCase("Bring home roughly two and a half grand monthly", {"monthly_net_income": 2500}),
    SetupCase(
        "My salary is 2.8k after tax and my rent is 1k",
        {"monthly_net_income": 2800, "monthly_expenses": 1000},
    ),
    SetupCase("I have 10,000 in shares and 2,000 in cash", {"investments": 10000, "cash": 2000}),
    SetupCase(
        "Need 8k for a car by March 2027",
        {"goal_target_amount": 8000, "goal_target_date": "2027-03-01", "goal_type": "vehicle"},
    ),
    SetupCase(
        "Earning 4000 a month net, my outgoings total 2500, I invest 500 monthly and have 30k "
        "in an index fund",
        {
            "monthly_net_income": 4000,
            "monthly_expenses": 2500,
            "monthly_investment_contribution": 500,
            "investments": 30000,
        },
    ),
    SetupCase(
        "I'm a student, I get 900 a month from a part-time job and spend 700",
        {"monthly_net_income": 900, "monthly_expenses": 700},
    ),
    SetupCase(
        "I rent out a room for 400 a month and my day job pays 2,300",
        {"other_monthly_income": 400, "monthly_net_income": 2300},
    ),
    SetupCase(
        "Goal: master's degree in 2029, about 25 thousand",
        {"goal_target_amount": 25000, "goal_target_date": "2029-01-01", "goal_type": "education"},
    ),
    SetupCase("I have nothing saved and about 3,000 of debt", {"cash": 0, "debt_balance": 3000}),
    SetupCase(
        "Monthly: income 2,600, expenses 1,900. Savings 15k. Want a 40k house deposit in 4 years.",
        {
            "monthly_net_income": 2600,
            "monthly_expenses": 1900,
            "cash": 15000,
            "goal_target_amount": 40000,
            "goal_target_date": "2030-10-01",
            "goal_type": "house",
        },
    ),
    SetupCase(
        "I'm 41 and I want 100k by 2035 to pay for my kids' university",
        {
            "age": 41,
            "goal_target_amount": 100000,
            "goal_target_date": "2035-01-01",
            "goal_type": "education",
        },
    ),
    SetupCase("Spending is roughly 1,750 per month including rent", {"monthly_expenses": 1750}),
    SetupCase(
        "I have 5k in my current account, 7k in a high-yield savings account and 20k in stocks",
        {"cash": 12000, "investments": 20000},
    ),
]


def score(draft: dict, expected: dict) -> tuple[int, int, int, list[str]]:
    """(correct, missing, wrong, details) over the scored fields. A field that should be
    empty but isn't counts as wrong: an invented value is worse than a missing one."""
    correct = missing = wrong = 0
    details = []
    for field in SCORED:
        want, got = expected.get(field), draft.get(field)
        if want is None and got is None:
            continue
        if want is not None and got is None:
            missing += 1
            details.append(f"{field}: missing (expected {want})")
        elif want is not None and _same(got, want):
            correct += 1
        else:
            wrong += 1
            details.append(f"{field}: got {got}, expected {want}")
    return correct, missing, wrong, details


def _same(got: object, want: object) -> bool:
    if isinstance(want, int | float) and isinstance(got, int | float):
        return abs(got - want) < 0.005
    return str(got) == str(want)
