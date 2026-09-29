"""The rule-based parser: phrasings -> structured intents. It copies amounts, never computes."""

import pytest

from app.agents.intents import (
    CompareScenarios,
    ExplainAssumptions,
    GoalDate,
    NeedsClarification,
    RequiredContribution,
    RunProjection,
    Unsupported,
    WhatIf,
)
from app.agents.mock_parser import parse_message


def overrides_of(message: str, previous=None) -> dict:
    intent = parse_message(message, previous)
    assert isinstance(intent, WhatIf), f"{message!r} -> {intent}"
    return intent.overrides.model_dump(exclude_none=True)


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("What if I invest €200 more per month?", {"monthly_investment_contribution_delta": 200}),
        (
            "what if i invested 200 euros extra each month",
            {"monthly_investment_contribution_delta": 200},
        ),
        ("What if I invest 1.5k more?", {"monthly_investment_contribution_delta": 1500}),
        ("What if I invest €100 less?", {"monthly_investment_contribution_delta": -100}),
        ("What if I invest €600 a month?", {"monthly_investment_contribution": 600}),
        ("What if I stop investing?", {"monthly_investment_contribution": 0}),
        ("What if I spend €200 less?", {"monthly_expenses_delta": -200}),
        ("what if I cut my expenses by 150", {"monthly_expenses_delta": -150}),
        ("What if my expenses were €1,500?", {"monthly_expenses": 1500}),
        ("What if I earn €3,000 a month?", {"monthly_net_income": 3000}),
        ("What if I get a raise of €300?", {"monthly_net_income_delta": 300}),
        ("What if returns are only 3%?", {"annual_return": 0.03}),
        ("What if my salary grows 4% a year?", {"annual_salary_growth": 0.04}),
        ("what if expenses rise 3.5 percent per year", {"annual_expense_growth": 0.035}),
        (
            "What if I invest €200 more and spend €100 less?",
            {"monthly_investment_contribution_delta": 200, "monthly_expenses_delta": -100},
        ),
    ],
)
def test_what_if_phrasings(message: str, expected: dict):
    assert overrides_of(message) == expected


def test_years_and_targets_are_not_amounts():
    assert overrides_of("What if I invest €200 more by 2030?") == {
        "monthly_investment_contribution_delta": 200
    }


class TestFollowUps:
    def test_new_amount_reuses_the_previous_field_and_direction(self):
        first = parse_message("What if I spend €200 less?")
        assert overrides_of("And with €300 instead?", first) == {"monthly_expenses_delta": -300}

    def test_rate_follow_up(self):
        first = parse_message("What if returns are 3%?")
        assert overrides_of("and 4%?", first) == {"annual_return": 0.04}

    def test_same_question_under_another_assumption_set(self):
        first = parse_message("What if I invest €200 more?")
        again = parse_message("And under conservative assumptions?", first)
        assert isinstance(again, WhatIf)
        assert again.assumption_set == "conservative"
        assert again.overrides == first.overrides

    def test_an_amount_without_context_asks_what_it_is_for(self):
        intent = parse_message("What if 200 more?")
        assert isinstance(intent, NeedsClarification)
        assert "monthly investment, your take-home pay or your expenses" in intent.question

    def test_a_percentage_without_context_asks_which_rate(self):
        intent = parse_message("what if it's 3%?")
        assert isinstance(intent, NeedsClarification)
        assert "investment return, the salary growth or the expense growth" in intent.question


@pytest.mark.parametrize(
    ("message", "intent_type"),
    [
        ("Am I on track?", RunProjection),
        ("Show me my projection", RunProjection),
        ("When will I reach my goal?", GoalDate),
        ("How long until I have enough?", GoalDate),
        ("How much do I need to invest each month?", RequiredContribution),
        ("How much should I save per month to reach the goal on time?", RequiredContribution),
        ("Compare my options", CompareScenarios),
        ("Show the scenarios side by side", CompareScenarios),
        ("What are you assuming?", ExplainAssumptions),
        ("Which rates do you use?", ExplainAssumptions),
    ],
)
def test_questions_about_the_plan(message: str, intent_type: type):
    assert isinstance(parse_message(message), intent_type)


def test_assumption_set_is_picked_up():
    intent = parse_message("Am I on track under pessimistic assumptions?")
    assert isinstance(intent, RunProjection)
    assert intent.assumption_set == "conservative"


@pytest.mark.parametrize(
    ("message", "reason"),
    [
        ("Should I buy an ETF?", "advice"),
        ("Which stocks are best?", "advice"),
        ("Should I invest €200 more?", "advice"),
        ("Do you recommend paying off debt first?", "advice"),
        ("How are taxes on gains calculated?", "out_of_scope"),
        ("Tell me a joke", "not_understood"),
        ("hello", "not_understood"),
    ],
)
def test_advice_and_out_of_scope_are_not_answered(message: str, reason: str):
    intent = parse_message(message)
    assert isinstance(intent, Unsupported)
    assert intent.reason == reason
