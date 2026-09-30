"""The rule-based parser: phrasings -> structured intents. It copies amounts, never computes."""

import pytest

from app.agents.intents import (
    CompareScenarios,
    ExplainAssumptions,
    GoalDate,
    Likelihood,
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


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("What if the market falls 30% next year?", {"first_year_return": -0.3}),
        ("what if markets crash 40%", {"first_year_return": -0.4}),
        ("What if there is a 25% crash?", {"first_year_return": -0.25}),
        ("What if my investments drop by 20%?", {"first_year_return": -0.2}),
        ("What if my portfolio grows 15% next year?", {"first_year_return": 0.15}),
        # Not one-off moves: a level, or a yearly rate
        ("What if returns fall to 2%?", {"annual_return": 0.02}),
        ("What if the market gives me 7% a year?", {"annual_return": 0.07}),
        # A change, not a new amount
        ("What if my income goes up by 300?", {"monthly_net_income_delta": 300}),
        ("What if my expenses go down by 100?", {"monthly_expenses_delta": -100}),
    ],
)
def test_market_moves_and_changes(message: str, expected: dict):
    """Regression: "the market falls 30%" used to become a +30% yearly return."""
    assert overrides_of(message) == expected


@pytest.mark.parametrize(
    "message",
    ["What if returns are 150%?", "What if the market falls 100%?"],
)
def test_rates_out_of_range_get_a_question_instead_of_an_error(message: str):
    intent = parse_message(message)
    assert isinstance(intent, NeedsClarification)
    assert "outside what the simulator accepts" in intent.question


class TestLikelihood:
    @pytest.mark.parametrize(
        "message",
        [
            "How likely am I to reach my goal?",
            "What are my chances?",
            "What's the probability of making it on time?",
            "How sure is this projection?",
        ],
    )
    def test_questions(self, message: str):
        intent = parse_message(message)
        assert isinstance(intent, Likelihood)
        assert intent.overrides is None

    def test_with_a_change(self):
        intent = parse_message("How likely am I to reach it if I invest €200 more?")
        assert isinstance(intent, Likelihood)
        assert intent.overrides.monthly_investment_contribution_delta == 200

    def test_how_likely_is_that_uses_the_previous_what_if(self):
        drop = parse_message("What if the market falls 30% next year?")
        intent = parse_message("How likely is that?", drop)
        assert isinstance(intent, Likelihood)
        assert intent.overrides == drop.overrides

    def test_a_new_amount_keeps_asking_how_likely(self):
        first = parse_message("How likely am I to get there if I invest €200 more?")
        intent = parse_message("And with €300?", first)
        assert isinstance(intent, Likelihood)
        assert intent.overrides.monthly_investment_contribution_delta == 300

    def test_under_another_assumption_set(self):
        intent = parse_message("And under optimistic assumptions?", parse_message("My chances?"))
        assert isinstance(intent, Likelihood)
        assert intent.assumption_set == "optimistic"

    def test_advice_is_still_declined(self):
        intent = parse_message("Should I sell my shares if the market falls 30%?")
        assert isinstance(intent, Unsupported)
        assert intent.reason == "advice"


def test_a_stock_market_what_if_is_not_advice():
    """Regression: "what ... stock" matched the advice rule, so a crash question was declined."""
    assert overrides_of("What if the stock market crashes 30%?") == {"first_year_return": -0.3}
    assert parse_message("What stocks should I buy before a crash of 30%?").kind == "unsupported"
