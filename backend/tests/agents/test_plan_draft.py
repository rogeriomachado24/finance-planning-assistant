"""Describe your plan, with the rules: description -> extraction -> draft -> next question.

The rules only copy numbers from the message; every calculation shown in the draft (parts
added, a year spread over 12 months, a percentage of a price) comes from the domain."""

from datetime import date
from decimal import Decimal

import pytest

from app.agents.grounding import as_number, numbers_in
from app.agents.plan_draft import (
    DONE,
    Answer,
    DraftReply,
    Extraction,
    apply_extraction,
    start,
)
from app.agents.plan_rules import extract_rules
from app.domain.models import GoalType

TODAY = date(2026, 10, 15)


def conversation(*messages: str) -> DraftReply:
    reply = start()
    for message in messages:
        reply = apply_extraction(reply.draft, extract_rules(message, reply.draft.asked), TODAY)
    return reply


class TestOneDescription:
    def test_a_full_description_fills_the_draft(self):
        reply = conversation(
            "I take home about 2,400 a month, spend 1,600, have 8k saved and 5k in an ETF. "
            "I want 60k for a house deposit by June 2032."
        )
        d = reply.draft
        assert (d.monthly_net_income, d.monthly_expenses) == (2400, 1600)
        assert (d.cash, d.investments) == (8000, 5000)
        assert (d.goal_target_amount, d.goal_target_date) == (60_000, date(2032, 6, 1))
        assert (d.goal_name, d.goal_type) == ("House deposit", GoalType.HOUSE)
        assert reply.complete
        assert reply.question.startswith("How much do you invest each month?")
        assert reply.optional_missing == ["Monthly investment", "Debt"]

    def test_the_arithmetic_is_the_domain_s_and_is_shown(self):
        reply = conversation(
            "I earn 36k a year. Rent is 900 and about 700 a month for everything else."
        )
        d = reply.draft
        assert d.monthly_net_income == 3000
        assert d.notes["monthly_net_income"] == "€36,000 a year ÷ 12"
        assert d.monthly_expenses == 1600
        assert d.notes["monthly_expenses"] == "€900 + €700"
        assert "Expenses: €1,600 a month (€900 + €700)" in reply.understood

    def test_an_amount_without_a_period_is_taken_as_monthly_and_says_so(self):
        reply = conversation("I take home 2,400")
        assert reply.draft.monthly_net_income == 2400
        assert reply.understood == ["Take-home pay: €2,400 a month (taken as per month)"]

    @pytest.mark.parametrize(
        ("message", "expected"),
        [
            ("I want 60k for a house by 2032", date(2032, 1, 1)),
            ("I want 60k for a house by June 2032", date(2032, 6, 1)),
            ("I want 60k for a house in 6 years", date(2032, 10, 1)),
            ("I want 60k for a house in 18 months", date(2028, 4, 1)),
        ],
    )
    def test_goal_dates(self, message: str, expected: date):
        d = conversation(message).draft
        assert d.goal_target_date == expected
        assert d.goal_target_amount == 60_000  # the year or "6 years" is never an amount

    def test_a_year_without_a_month_says_which_day_it_means(self):
        reply = conversation("I want 60k for a house by 2032")
        assert "Goal date: 1 Jan 2032 (no month given, so 1 January)" in reply.understood

    @pytest.mark.parametrize(
        ("message", "field", "value"),
        [
            ("I have 1.5k saved", "cash", 1500),
            ("My outgoings are around 2.200 per month", "monthly_expenses", 2200),
            ("I have €12,000 in the bank", "cash", 12_000),
            ("My portfolio is worth 20 thousand", "investments", 20_000),
            ("I invest 300 a month", "monthly_investment_contribution", 300),
            ("I get 400 a month in rental income", "other_monthly_income", 400),
            ("I owe 4,000 on a car loan", "debt_balance", 4000),
        ],
    )
    def test_phrasings(self, message: str, field: str, value: float):
        assert getattr(conversation(message).draft, field) == value

    def test_age_and_take_home_are_not_mistaken(self):
        d = conversation("I'm 32 and my take-home pay is 2,500 a month").draft
        assert d.age == 32
        assert d.monthly_net_income == 2500
        assert d.goal_type is None  # "take-home" is not a home
        assert conversation("I'm 32k in debt").draft.age is None

    def test_a_loan_and_its_payment(self):
        d = conversation("I have a car loan of 4,000 and pay 200 a month on it").draft
        assert (d.debt_balance, d.monthly_debt_payment) == (4000, 200)

    def test_said_to_be_nothing(self):
        d = conversation("No savings, I don't invest and I'm debt free").draft
        assert (d.cash, d.monthly_investment_contribution, d.debt_balance) == (0, 0, 0)


class TestPercentageOfAPrice:
    def test_the_domain_works_it_out_and_the_user_confirms(self):
        reply = conversation("I'd like a 20% deposit on a 300k flat in 6 years")
        assert reply.draft.goal_target_amount is None  # not until confirmed
        assert reply.question.startswith("So the goal is €60,000 (20% of €300,000)?")

        confirmed = conversation("I'd like a 20% deposit on a 300k flat in 6 years", "yes")
        assert confirmed.draft.goal_target_amount == 60_000
        assert "Goal amount: €60,000 (20% of €300,000)" in confirmed.understood

    def test_another_amount_replaces_it(self):
        d = conversation("I want a 10% deposit for a 250,000 house", "no, 30k").draft
        assert d.goal_target_amount == 30_000
        assert d.pending_goal_amount is None


class TestQuestions:
    def test_the_first_question_is_take_home_pay(self):
        reply = start()
        assert reply.question == "How much do you take home each month, after tax?"
        assert reply.still_missing == [
            "Take-home pay",
            "Expenses",
            "Goal amount",
            "Goal date",
            "Goal name",
        ]
        assert not reply.complete

    def test_short_answers_go_to_the_question_asked(self):
        reply = conversation("2400", "1600")
        assert (reply.draft.monthly_net_income, reply.draft.monthly_expenses) == (2400, 1600)
        assert reply.question == "How much do you want to save for your goal?"

    def test_no_and_skip(self):
        base = "I take home 2,400 a month, spend 1,600 a month, want 60k for a house by 2032"
        reply = conversation(base, "no", "skip")
        assert reply.draft.cash == 0
        assert reply.draft.investments is None
        assert "investments" in reply.draft.skipped
        assert reply.question.startswith("How much do you invest each month?")

    def test_debt_payment_is_asked_only_when_there_is_debt(self):
        base = "I take home 2,400 a month, spend 1,600 a month, want 60k for a house by 2032"
        no_debt = conversation(base, "0", "0", "0", "no")
        assert no_debt.question == DONE
        with_debt = conversation(base, "0", "0", "0", "5k")
        assert with_debt.question == "How much do you pay on that debt each month?"

    def test_the_goal_name_is_the_answer_in_the_person_s_words(self):
        base = "I take home 2,400 a month, spend 1,600 a month and want 10k by 2028"
        assert conversation(base).question.startswith("What should the goal be called?")
        reply = conversation(base, "Round the world trip")
        assert reply.draft.goal_name == "Round the world trip"
        assert reply.draft.goal_type is GoalType.TRAVEL  # still recognised from the words

    def test_a_later_message_corrects_an_earlier_one(self):
        d = conversation("I spend 1,600 a month", "actually I spend 1,800 a month").draft
        assert d.monthly_expenses == 1800


DESCRIPTIONS = [
    "I take home about 2,400 a month, spend 1,600, have 8k saved and 5k in an ETF. "
    "I want 60k for a house deposit by June 2032.",
    "I earn 36k a year. Rent is 900 and about 700 for everything else. I'm 29.",
    "Saving for a wedding in June 2028, need 15000. I make 3100 after tax.",
    "I have a car loan of 4,000 and pay 200 a month on it, and 1.5k in savings",
    "My outgoings are around 2.200 per month and I invest 150 monthly in an index fund",
]


@pytest.mark.parametrize("message", DESCRIPTIONS)
def test_every_extracted_number_is_written_in_the_message(message: str):
    """The rules copy numbers; they never produce one that isn't in the text."""
    written = numbers_in(message)
    found = extract_rules(message)
    for amount in found.amounts:
        for part in amount.parts:
            assert as_number(part) in written, f"{part} is not in {message!r}"


def test_the_number_check_reads_thousands_as_written():
    assert {Decimal("2200"), Decimal("2.2")} <= numbers_in("around 2.200 per month")
    assert Decimal("20000") in numbers_in("worth 20 thousand")
    assert Decimal("1200000") in numbers_in("a 1.2m house")
    assert Decimal("5") in numbers_in("in 5 months")  # "m" only as a unit on its own


def test_an_extraction_is_plain_data():
    """What a language model would fill in (step 2) is the same structure."""
    found = Extraction(answer=Answer.YES)
    assert apply_extraction(start().draft, found, TODAY).understood == []
