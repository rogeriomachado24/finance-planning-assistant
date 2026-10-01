"""Summaries worded by the model: accepted only when every figure is copied from the facts
and nothing reads like advice; otherwise the facts are shown as they are."""

import pytest

from app.agents.providers import MockProvider
from tests.agents.test_ollama_provider import FakeModel, provider_with

FACTS = [
    "Under these assumptions, you reach the €80,000 goal on 1 Aug 2031, 10 months before the "
    "target date (1 Jun 2032).",
    "In about 93% of 1,000 simulated futures, the goal is reached by 1 Jun 2032.",
    "To be on time in 9 of 10 futures, about €826 a month would need to be invested; today "
    "€400 is invested each month.",
]


def test_without_a_model_the_facts_are_the_summary():
    worded = MockProvider().summarise(FACTS)
    assert (worded.text, worded.source) == (" ".join(FACTS), "template")


def test_the_model_is_not_asked_unless_rewording_is_on():
    model = FakeModel()
    worded = provider_with(writer=model).summarise(FACTS)
    assert (worded.source, model.calls) == ("template", 0)


def test_a_faithful_rewording_is_used():
    text = (
        "You're on course to reach €80,000 on 1 Aug 2031, 10 months before your target date. "
        "In about 93% of 1,000 simulated futures you get there by 1 Jun 2032. Being on time in "
        "9 of 10 futures would take about €826 a month, compared with €400 today."
    )
    provider = provider_with(writer=FakeModel(text), rewrite=True)
    worded = provider.summarise(FACTS)
    assert (worded.text, worded.source) == (text, "phi3")


@pytest.mark.parametrize(
    "text",
    [
        "You reach €80,000 on 1 Aug 2031, with €850 a month needed for 9 of 10.",  # invented
        "You should invest €826 a month to be safe.",  # advice
        "In 95% of 1,000 simulated futures you reach it by 1 Jun 2032.",  # changed share
        "You'll reach it about a year early.",  # a duration in words
        "In 8 of 10 futures you need €826 a month.",  # a share that isn't in the facts
        # Real qwen2.5:3b output that passed the figure checks: success inverted into failure
        "This shortfall occurred in fewer than one out of every thousand simulated scenarios.",
    ],
)
def test_a_rewording_that_fails_a_check_falls_back_to_the_facts(text: str):
    worded = provider_with(writer=FakeModel(text), rewrite=True).summarise(FACTS)
    assert (worded.text, worded.source) == (" ".join(FACTS), "template")


def test_a_model_error_falls_back_to_the_facts():
    worded = provider_with(writer=FakeModel(ConnectionError("down")), rewrite=True).summarise(FACTS)
    assert worded.source == "template"
