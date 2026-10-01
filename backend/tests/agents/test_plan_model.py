"""The model's part in "describe your plan": its form is checked against the message, it is
asked only when the rules missed something, and where both answer the rules win."""

import copy
import json

from app.agents.ollama import OllamaProvider
from app.agents.plan_draft import Amount, Extraction, GoalDate
from app.agents.plan_model import ModelPlanForm, merge, rules_missed_something, to_extraction
from app.agents.plan_rules import extract_rules
from app.domain.models import GoalType
from app.domain.plan_input import Period
from tests.agents.test_ollama_provider import FakeModel

_BASE = None


def reader(*replies) -> tuple[OllamaProvider, FakeModel]:
    global _BASE
    _BASE = _BASE or OllamaProvider("qwen2.5:3b", "http://127.0.0.1:1")
    provider = copy.copy(_BASE)
    model = FakeModel(*replies)
    provider._plan_reader = model
    return provider, model


def amounts(found: Extraction) -> dict[str, tuple[list[float], Period | None]]:
    return {a.field: (a.parts, a.period) for a in found.amounts}


class TestChecks:
    def test_amounts_written_in_the_message_are_kept_with_their_parts(self):
        form = ModelPlanForm(
            take_home_pay=[2500], take_home_pay_period="month", expenses=[900, 400]
        )
        found = to_extraction(form, "I bring home 2,500 a month; rent 900 and 400 for food")
        assert amounts(found) == {
            "monthly_net_income": ([2500], Period.MONTH),
            "monthly_expenses": ([900, 400], None),
        }

    def test_an_amount_not_in_the_message_is_dropped_not_guessed(self):
        """E.g. the model adding "rent 900 and food 400" up to 1300 itself."""
        form = ModelPlanForm(take_home_pay=[2500], expenses=[1300])
        found = to_extraction(form, "I bring home 2,500; rent 900 and 400 for food")
        assert amounts(found) == {"monthly_net_income": ([2500], None)}

    def test_a_yearly_period_needs_year_words_in_the_message(self):
        form = ModelPlanForm(take_home_pay=[2500], take_home_pay_period="year")
        assert amounts(to_extraction(form, "I bring home 2,500"))["monthly_net_income"] == (
            [2500],
            None,
        )
        found = to_extraction(form, "I bring home 2,500 annually")
        assert amounts(found)["monthly_net_income"] == ([2500], Period.YEAR)

    def test_a_month_needs_a_month_name(self):
        form = ModelPlanForm(goal_amount=8000, goal_year=2027, goal_month=3)
        assert to_extraction(form, "8k for a car in 2027").goal_date == GoalDate(year=2027)
        assert to_extraction(form, "8k for a car by March 2027").goal_date == GoalDate(
            year=2027, month=3
        )

    def test_a_percentage_of_a_price_is_left_to_the_domain(self):
        form = ModelPlanForm(goal_percent_of_price=15, goal_price=400_000, goal_kind="house")
        found = to_extraction(form, "a 15% down payment on a 400k home")
        assert (found.goal_share.percent, found.goal_share.price) == (15, 400_000)
        assert found.goal_type is GoalType.HOUSE
        invented = ModelPlanForm(goal_amount=60_000)  # "20% of 300k" worked out by the model
        assert to_extraction(invented, "a 20% deposit on a 300k flat").amounts == []


class TestWhenToAsk:
    def test_not_when_the_rules_used_every_number(self):
        message = "I take home 2,400 a month and spend 1,600"
        assert not rules_missed_something(message, extract_rules(message))

    def test_when_a_number_is_left_unexplained(self):
        message = "Bring home 2,500 monthly"
        assert rules_missed_something(message, extract_rules(message))

    def test_a_european_thousands_number_counts_as_used(self):
        message = "My outgoings are around 2.200 per month"
        assert not rules_missed_something(message, extract_rules(message))

    def test_not_for_short_answers(self):
        assert not rules_missed_something("no", extract_rules("no", "debt_balance"))


class TestMerge:
    def test_the_rules_win_and_the_model_fills_the_rest(self):
        rules = Extraction(amounts=[Amount(field="monthly_expenses", parts=[1600])])
        model = Extraction(
            amounts=[
                Amount(field="monthly_expenses", parts=[1700]),
                Amount(field="monthly_net_income", parts=[2500]),
            ],
            goal_type=GoalType.TRAVEL,
        )
        merged = merge(rules, model)
        assert amounts(merged) == {
            "monthly_expenses": ([1600], None),
            "monthly_net_income": ([2500], None),
        }
        assert merged.goal_type is GoalType.TRAVEL


class TestReadPlan:
    def test_rules_only_when_they_explain_every_number(self):
        provider, model = reader()
        read = provider.read_plan("I take home 2,400 a month and spend 1,600", None)
        assert (read.source, model.calls) == ("rules", 0)

    def test_the_model_adds_what_the_rules_missed(self):
        provider, model = reader(json.dumps({"take_home_pay": [2500]}))
        read = provider.read_plan("Bring home 2,500 monthly", None)
        assert read.source == "qwen2.5:3b"
        assert amounts(read.extraction)["monthly_net_income"] == ([2500], None)
        assert model.calls == 1

    def test_falls_back_to_the_rules_when_the_model_fails(self):
        provider, _ = reader(ConnectionError("Ollama is not running"))
        read = provider.read_plan("Bring home 2,500 monthly", None)
        assert read.source == "rules"

    def test_a_rejected_answer_leaves_the_rules_result(self):
        provider, _ = reader(json.dumps({"take_home_pay": [2600]}))  # not in the message
        read = provider.read_plan("Bring home 2,500 monthly", None)
        assert read.source == "rules"
        assert read.extraction == extract_rules("Bring home 2,500 monthly")


def test_values_read_by_the_model_are_marked_for_review():
    """The model's misreadings in the evaluation (a trip budget read as monthly spending)
    pass every number check, so the person is asked to check exactly those fields."""
    from datetime import date

    from app.agents.plan_draft import apply_extraction, start

    provider, _ = reader(json.dumps({"take_home_pay": [2500]}))
    read = provider.read_plan("I take home 1,900 a month. Bring home 2,500 monthly in total", None)
    assert read.extraction.from_model == []  # the rules had take-home pay: theirs wins

    provider, _ = reader(json.dumps({"take_home_pay": [2500], "age": 30}))
    read = provider.read_plan("Bring home 2,500 monthly, I'm thirty and 30 next week", None)
    reply = apply_extraction(start().draft, read.extraction, date(2026, 10, 15))
    assert "monthly_net_income" in reply.draft.to_check
    assert "Take-home pay: €2,500 a month (taken as per month) · read by the AI, please check" in (
        reply.understood
    )
