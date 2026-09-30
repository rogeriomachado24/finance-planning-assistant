"""The Ollama provider's guardrails, tested with a fake model (no Ollama needed).

The failing explanations below are real phi3 outputs from a live run: each passed a
digits-only check, and each is wrong.
"""

import copy
import os

import pytest
from langchain_core.messages import AIMessage

from app.agents.eval_set import CASES, matches
from app.agents.explain import DISCLAIMER, Facts, template_body
from app.agents.intents import (
    ExplainAssumptions,
    NeedsClarification,
    RunProjection,
    Unsupported,
    WhatIf,
)
from app.agents.mock_parser import parse_message
from app.agents.ollama import (
    ModelRequest,
    OllamaProvider,
    UntrustedOutput,
    check_explanation,
    to_intent,
)
from app.schemas.plan import Rates
from app.schemas.scenarios import ComparedScenarioOut


class TestToIntent:
    def test_copies_amounts_and_converts_percentages(self):
        request = ModelRequest(spending_change_eur=-250, return_percent=3, kind="what_if")
        intent = to_intent(request, "What if I trim spending by 250 and returns are 3%?")
        assert isinstance(intent, WhatIf)
        assert intent.overrides.monthly_expenses_delta == -250
        assert intent.overrides.annual_return == 0.03

    @pytest.mark.parametrize(
        "request_",
        [
            ModelRequest(invest_change_eur=-0.025, kind="what_if"),  # phi3 invented this
            ModelRequest(return_percent=0.03, kind="what_if"),  # 3% given as 0.03
            ModelRequest(pay_new_eur=3500, kind="what_if"),
        ],
    )
    def test_rejects_numbers_that_are_not_in_the_message(self, request_):
        with pytest.raises(UntrustedOutput, match="not in the message"):
            to_intent(request_, "What if returns are only 3% and I earn 3000?")

    def test_zero_only_when_the_user_stops(self):
        stop = ModelRequest(invest_new_eur=0, kind="what_if")
        assert isinstance(to_intent(stop, "What if I stop investing?"), WhatIf)
        with pytest.raises(UntrustedOutput):
            to_intent(stop, "What if I invest differently?")

    def test_rejects_an_assumption_set_the_user_did_not_name(self):
        with pytest.raises(UntrustedOutput, match="not named"):
            to_intent(ModelRequest(assumptions="conservative", kind="goal_date"), "How long?")
        named = ModelRequest(assumptions="conservative", kind="goal_date")
        assert (
            to_intent(named, "How long in the pessimistic case?").assumption_set == "conservative"
        )

    def test_a_described_change_makes_it_a_what_if(self):
        request = ModelRequest(invest_change_eur=200, kind="on_track")
        assert isinstance(to_intent(request, "on track if I invest 200 more?"), WhatIf)

    def test_what_if_without_a_change_is_rejected(self):
        with pytest.raises(UntrustedOutput):
            to_intent(ModelRequest(kind="what_if"), "what if things change?")


class FakeModel:
    """Stands in for ChatOllama: returns canned replies and records the calls."""

    def __init__(self, *replies: str):
        self.replies = list(replies)
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return AIMessage(content=reply)


_BASE = None


def provider_with(parser=None, writer=None, rewrite=False) -> OllamaProvider:
    """A provider whose models are fakes. Built once (ChatOllama clients take ~0.7 s each),
    then copied per test."""
    global _BASE
    _BASE = _BASE or OllamaProvider("phi3", "http://127.0.0.1:1")
    provider = copy.copy(_BASE)
    provider.rewrite_replies = rewrite
    provider._parser = parser or FakeModel()
    provider._writer = writer or FakeModel()
    return provider


class TestParse:
    def test_rules_first_the_model_is_not_asked(self):
        model = FakeModel()
        parsed = provider_with(parser=model).parse("Am I on track?", None)
        assert isinstance(parsed.intent, RunProjection)
        assert parsed.source == "rules"
        assert model.calls == 0

    def test_the_model_handles_what_the_rules_cannot_place(self):
        model = FakeModel('{"kind": "assumptions"}')
        parsed = provider_with(parser=model).parse("Which growth rates are you using?", None)
        assert isinstance(parsed.intent, ExplainAssumptions)
        assert parsed.source == "phi3"

    @pytest.mark.parametrize(
        "reply",
        ['{"kind": "unknown_kind"}', "not json", ConnectionError("Ollama is not running")],
    )
    def test_falls_back_to_the_rules_when_the_model_fails(self, reply):
        parsed = provider_with(parser=FakeModel(reply)).parse("Tell me a joke", None)
        assert parsed.source == "rules"
        assert isinstance(parsed.intent, Unsupported)

    def test_a_clarifying_question_beats_a_model_refusal(self):
        parsed = provider_with(parser=FakeModel('{"kind": "other"}')).parse(
            "What if 200 more?", None
        )
        assert isinstance(parsed.intent, NeedsClarification)


FACTS_TEXT = (
    "With €200 more invested each month, the goal is reached on 1 Jun 2031, 1 month earlier "
    "than the current plan (1 Jul 2031). On the target date (1 Jun 2032) the projection shows "
    "€94,059, +€2,098 compared with the current plan."
)


class TestCheckExplanation:
    def test_a_faithful_rewording_passes(self):
        check_explanation(
            "Investing €200 more each month gets you to the goal on 1 Jun 2031, 1 month earlier "
            "than the current plan. By 1 Jun 2032 you'd have €94,059 (+€2,098).",
            FACTS_TEXT,
        )

    @pytest.mark.parametrize(
        ("reply", "why"),
        [
            (  # real phi3 output: invented date made of digits found elsewhere in the facts
                "If you invest an additional €200 per month, your savings goal could be reached "
                "a month earlier than planned on June 1, 2031! By doing so, by January 1, 2032, "
                "there would have been an increase of €2,098.",
                "not copied as written",
            ),
            (  # real phi3 output: "a month" where the facts say 11 months
                "You're projected to reach €80,000 by 1 Jul 2031, which is just a month before "
                "the target date.",
                "not copied|in words",
            ),
            ("That's €95,000 by the target date.", "not in the facts"),
            ("You should invest the extra €200.", "advice"),
            ("Keep up the good work with €200 more!", "advice"),
        ],
    )
    def test_rejects_real_failure_modes(self, reply: str, why: str):
        with pytest.raises(UntrustedOutput, match=why):
            check_explanation(
                reply, FACTS_TEXT + " You reach €80,000 on 1 Jul 2031, 11 months early."
            )


def facts() -> Facts:
    result = {
        "scenario_name": "Current plan",
        "profile": {
            "monthly_net_income": 2500,
            "monthly_expenses": 1700,
            "cash": 10000,
            "investments": 15000,
            "monthly_investment_contribution": 400,
            "other_monthly_income": 0,
            "debt_balance": 0,
            "monthly_debt_payment": 0,
            "age": 32,
        },
        "assumptions": {
            "annual_return": 0.05,
            "annual_salary_growth": 0.02,
            "annual_expense_growth": 0.02,
            "annual_inflation": 0.02,
        },
        "monthly_contribution": 400,
        "monthly_surplus": 800,
        "target_amount": 80000,
        "target_date": "2032-06-01",
        "months_to_target_date": 69,
        "projected_goal_date": "2031-07-01",
        "months_to_goal": 58,
        "projected_value_at_target_date": 91961.6,
        "reaches_goal": True,
        "shortfall": 0,
        "required_monthly_contribution": 630.81,
        "goal_progress": {"current_amount": 25000, "remaining": 55000, "fraction": 0.3125},
        "warnings": [],
        "snapshots": [],
    }
    compared = ComparedScenarioOut.model_validate(
        {
            "name": "Current plan",
            "description": "",
            "saved_id": None,
            "result": result,
            "vs_baseline": {"goal_months_earlier": 0, "value_at_target_difference": 0},
        }
    )
    return Facts(
        intent=RunProjection(),
        results=[compared],
        assumption_set="base",
        rates=Rates(annual_return=0.05, annual_salary_growth=0.02, annual_expense_growth=0.02),
        question="Am I on track?",
    )


class TestExplain:
    def test_templates_by_default_the_model_is_not_asked(self):
        writer = FakeModel()
        worded = provider_with(writer=writer).explain(facts())
        assert worded.source == "template"
        assert writer.calls == 0

    def test_an_accepted_rewording_gets_the_footer_from_code(self):
        writer = FakeModel("Good news: you reach the €80,000 goal on 1 Jul 2031, 11 months early.")
        worded = provider_with(writer=writer, rewrite=True).explain(facts())
        assert worded.source == "phi3"
        assert worded.text.endswith(DISCLAIMER)

    def test_a_rejected_rewording_falls_back_to_the_template(self):
        writer = FakeModel("You'll get there a month before the target date!")
        worded = provider_with(writer=writer, rewrite=True).explain(facts())
        assert worded.source == "template"
        assert template_body(facts()) in worded.text


@pytest.mark.skipif(
    os.environ.get("OLLAMA_TESTS") != "1", reason="set OLLAMA_TESTS=1 to run against a real model"
)
def test_real_model_does_not_make_parsing_worse():
    """With a real model, the app's strategy must score at least as well as the rules alone."""
    provider = OllamaProvider(os.environ.get("OLLAMA_MODEL", "phi3"), "http://127.0.0.1:11434")

    def score(parse) -> int:
        total = 0
        for case in CASES:
            previous = parse(case.previous, None) if case.previous else None
            total += matches(parse(case.message, previous).model_dump(mode="json"), case.expected)
        return total

    assert score(lambda m, p: provider.parse(m, p).intent) >= score(parse_message)
