"""The chat workflow end to end with the mock provider: message -> intent -> services ->
explanation, against a real (temporary) database."""

import re
from itertools import count

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.agents.explain import DISCLAIMER, NEEDS_PLAN, eur, percent, share
from app.agents.graph import build_chat_graph
from app.agents.providers import MockProvider
from app.db.session import create_session_factory
from app.services.assumptions import ensure_assumption_presets
from app.services.profile import get_profile
from tests.sample_plan import PROFILE, TODAY

_threads = count()


class Chat:
    """One conversation (thread) with the graph."""

    def __init__(self, graph):
        self.graph = graph
        self.config = {"configurable": {"thread_id": f"t{next(_threads)}"}}

    def say(self, message: str, assumption_set: str = "base") -> dict:
        return self.graph.invoke(
            {
                "message": message,
                "today": TODAY.isoformat(),
                "default_assumption_set": assumption_set,
            },
            self.config,
        )


@pytest.fixture
def graph(engine: Engine):
    return build_chat_graph(create_session_factory(engine), MockProvider())


@pytest.fixture
def chat(graph, plan: Session) -> Chat:
    return Chat(graph)


def euro_amounts(text: str) -> set[str]:
    return set(re.findall(r"−?€\d{1,3}(?:,\d{3})*", text))


def engine_amounts(state: dict) -> set[str]:
    """Every euro amount the engine returned (as displayed), plus those the user typed."""
    values: list[float] = []
    for r in state["results"]:
        res = r["result"]
        values += [
            res["target_amount"],
            res["projected_value_at_target_date"],
            res["shortfall"],
            res["monthly_contribution"],
            res["monthly_surplus"],
            r["vs_baseline"]["value_at_target_difference"],
            abs(r["vs_baseline"]["value_at_target_difference"]),
        ]
        if res["required_monthly_contribution"] is not None:
            values.append(res["required_monthly_contribution"])
    for f in (state.get("futures") or {}).get("scenarios", []):
        values += [f["value_at_target_date"][p] for p in ("p10", "p50", "p90")]
        if f["shortfall_when_missed"]:
            values += [f["shortfall_when_missed"][p] for p in ("p10", "p50", "p90")]
    overrides = state["intent"].get("overrides") or {}
    values += [abs(v) for v in overrides.values() if v is not None]
    return {eur(v) for v in values}


def engine_percentages(state: dict) -> set[str]:
    """Every percentage the engine returned or the user asked about, as written in replies."""
    values = list((state.get("assumptions") or {}).values())
    futures = state.get("futures") or {}
    if futures:
        values.append(futures["volatility"])
    overrides = state["intent"].get("overrides") or {}
    values += [abs(v) for k, v in overrides.items() if v is not None and k.startswith("annual_")]
    if overrides.get("first_year_return") is not None:
        values.append(abs(overrides["first_year_return"]))
    found = {percent(v) for v in values if v is not None}
    for f in futures.get("scenarios", []):
        for p in (f["probability_by_target_date"], f["not_reached_share"]):
            found.add(share(p).split()[-1])
    return found | {"80%"}  # "the middle 80% of futures" is a fixed definition


def assert_grounded(state: dict) -> None:
    """The reply contains no euro amount or percentage that the engine (or the user)
    didn't provide."""
    invented = euro_amounts(state["reply"]) - engine_amounts(state)
    assert not invented, f"reply mentions amounts not in the results: {invented}"
    invented = set(re.findall(r"\d+(?:\.\d+)?%", state["reply"])) - engine_percentages(state)
    assert not invented, f"reply mentions percentages not in the results: {invented}"


class TestAnswers:
    def test_what_if_runs_the_engine_and_explains_its_numbers(self, chat: Chat, plan: Session):
        state = chat.say("What if I invest €200 more per month?")

        assert state["status"] == "answered"
        current, what_if = state["results"]
        assert current["name"] == "Current plan"
        assert what_if["result"]["monthly_contribution"] == 600
        assert what_if["vs_baseline"]["goal_months_earlier"] >= 0
        assert "€200 more invested each month" in state["reply"]
        assert DISCLAIMER in state["reply"]
        assert_grounded(state)
        assert get_profile(plan) == PROFILE  # a what-if never changes the plan

    def test_follow_up_builds_on_the_previous_question(self, chat: Chat):
        chat.say("What if I invest €200 more per month?")
        state = chat.say("And with €300 instead?")
        assert state["results"][1]["result"]["monthly_contribution"] == 700
        assert_grounded(state)

    def test_conversations_are_separate(self, graph, chat: Chat):
        chat.say("What if I invest €200 more per month?")
        other = Chat(graph).say("And with €300 instead?")
        assert other["status"] == "clarification"

    @pytest.mark.parametrize(
        "message",
        [
            "Am I on track?",
            "When will I reach my goal?",
            "How much do I need to invest each month?",
            "Compare my options",
        ],
    )
    def test_plan_questions_are_grounded(self, chat: Chat, message: str):
        state = chat.say(message)
        assert state["status"] == "answered"
        assert state["results"]
        assert_grounded(state)
        assert "you should" not in state["reply"].lower()

    def test_required_contribution_quotes_the_engine(self, chat: Chat):
        state = chat.say("How much do I need to invest each month?")
        required = state["results"][0]["result"]["required_monthly_contribution"]
        assert eur(required) in state["reply"]

    def test_compare_lists_every_scenario(self, chat: Chat):
        state = chat.say("Compare my options")
        names = [r["name"] for r in state["results"]]
        assert names == ["Current plan", "Higher contribution", "Higher income"]
        assert all(name in state["reply"] for name in names)

    def test_named_assumption_set_is_used(self, chat: Chat, plan: Session):
        ensure_assumption_presets(plan)
        state = chat.say("What are the conservative assumptions?")
        assert state["assumption_set"] == "conservative"
        assert state["assumptions"]["annual_return"] == 0.02
        assert "2% investment return" in state["reply"]


class TestLikelihood:
    def test_answers_from_simulated_futures(self, chat: Chat):
        state = chat.say("How likely am I to reach my goal?")

        assert state["status"] == "answered"
        (plan,) = state["futures"]["scenarios"]
        assert plan["name"] == "Current plan"
        assert (
            f"In {share(plan['probability_by_target_date'])} of 1,000 simulated futures"
            in (state["reply"])
        )
        assert "precision ±" in state["reply"]
        assert "medium investment risk" in state["reply"]
        assert DISCLAIMER in state["reply"]
        assert_grounded(state)

    def test_likelihood_of_a_what_if_is_compared_with_the_plan(self, chat: Chat):
        state = chat.say("How likely am I to reach it if my income goes up by 300 a month?")

        plan, what_if = state["futures"]["scenarios"]
        assert what_if["probability_difference"] >= 0  # the same futures, more money
        assert "€300 more take-home pay a month" in state["reply"]
        assert "than with the current plan" in state["reply"]
        assert_grounded(state)

    def test_market_drop_then_how_likely(self, chat: Chat):
        drop = chat.say("What if the market falls 30% next year?")
        assert drop["intent"]["overrides"]["first_year_return"] == -0.3
        assert "a 30% fall in investments in the first year" in drop["reply"]
        assert "How likely is that?" in drop["reply"]
        assert_grounded(drop)

        state = chat.say("How likely is that?")
        assert state["intent"]["kind"] == "likelihood"
        assert state["intent"]["overrides"]["first_year_return"] == -0.3
        plan, what_if = state["futures"]["scenarios"]
        assert what_if["probability_difference"] < 0
        assert "fewer than with the current plan" in state["reply"]
        assert_grounded(state)

    def test_under_another_assumption_set(self, chat: Chat, plan: Session):
        ensure_assumption_presets(plan)
        chat.say("What are my chances?")
        state = chat.say("And under conservative assumptions?")
        assert state["intent"]["kind"] == "likelihood"
        assert state["futures"]["assumption_set"] == "conservative"
        assert_grounded(state)


class TestNotAnswered:
    def test_advice_is_declined_without_running_anything(self, chat: Chat):
        state = chat.say("Should I buy an ETF?")
        assert state["status"] == "declined"
        assert state["results"] == []
        assert "can't recommend" in state["reply"]

    def test_impossible_change_is_explained(self, chat: Chat):
        state = chat.say("What if I spend €5,000 less?")
        assert state["status"] == "clarification"
        assert "couldn't run that scenario" in state["reply"]

    def test_a_rate_out_of_range_gets_a_question(self, chat: Chat):
        state = chat.say("What if returns are 150%?")
        assert state["status"] == "clarification"
        assert "outside what the simulator accepts" in state["reply"]

    def test_unclear_amount_gets_a_question(self, chat: Chat):
        state = chat.say("What if 200 more?")
        assert state["status"] == "clarification"
        assert "monthly investment" in state["reply"]

    def test_missing_plan_is_explained(self, graph):
        state = Chat(graph).say("Am I on track?")
        assert state["status"] == "clarification"
        assert state["reply"] == NEEDS_PLAN

    def test_a_declined_turn_does_not_reset_the_follow_up(self, chat: Chat):
        chat.say("What if I spend €200 less?")
        chat.say("Should I buy an ETF?")
        state = chat.say("And with €300 instead?")
        assert state["intent"]["overrides"]["monthly_expenses_delta"] == -300


def test_comparison_lines_read_naturally(chat: Chat):
    """Regression: a scenario reaching the goal in the same month read "(at the same time as)"."""
    reply = chat.say("Compare my options")["reply"]
    assert "(same time)" in reply or "earlier)" in reply
    assert "as)" not in reply
    assert "than)" not in reply


def test_a_lower_share_from_investing_more_is_explained(chat: Chat):
    """Moving cash into investments can lower the share on the same futures (see the
    Phase 2 design); a reply saying so without a reason would read like an error."""
    state = chat.say("How likely am I to reach it if I invest 200 more?")
    what_if = state["futures"]["scenarios"][1]
    assert what_if["probability_difference"] < 0
    assert "moves money from cash" in state["reply"]
    assert_grounded(state)
