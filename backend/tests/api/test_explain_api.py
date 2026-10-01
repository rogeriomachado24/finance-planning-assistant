"""'What does this mean for me?' over HTTP, with the mock provider: the facts come from the
engine, and the summary is the facts themselves (no model)."""

import re

from fastapi.testclient import TestClient

from tests.api.conftest import GOAL_JSON, PROFILE_JSON


def test_projection_summary_from_the_engine(plan_client: TestClient):
    body = plan_client.post("/explain/projection", json={}).json()
    projection = plan_client.post("/simulate", json={}).json()
    futures = plan_client.post("/simulate/uncertainty", json={}).json()

    facts = body["facts"]
    assert facts[0].startswith("Under these assumptions, you reach the €80,000 goal on 1 Aug 2031")
    assert "of 1,000 simulated futures, the goal is reached by 1 Jun 2032." in facts[1]
    assert facts[2].startswith("To be on time in 9 of 10 futures, about €")
    nine = next(x for x in futures["required_monthly_investment"] if x["share"] == 0.9)
    assert f"€{round(nine['monthly_amount']):,}" in facts[2]
    assert f"today €{round(projection['monthly_contribution']):,} is invested" in facts[2]
    assert body["summary"] == " ".join(facts)
    assert body["worded_by"] == "template"


def test_a_plan_behind_target_says_how_short(plan_client: TestClient):
    plan_client.post("/goals", json=GOAL_JSON | {"target_amount": 120_000}).raise_for_status()
    facts = plan_client.post("/explain/projection", json={}).json()["facts"]
    assert "is not reached by 1 Jun 2032" in facts[0]
    assert any(f.startswith("In the futures that miss the target date") for f in facts)


def test_a_goal_already_covered_needs_no_more_facts(plan_client: TestClient):
    plan_client.put("/profile", json=PROFILE_JSON | {"cash": 90_000}).raise_for_status()
    facts = plan_client.post("/explain/projection", json={}).json()["facts"]
    assert facts == ["Your cash and investments already cover the €80,000 goal."]


def test_every_figure_in_the_summary_is_in_the_facts(plan_client: TestClient):
    body = plan_client.post("/explain/projection", json={"assumption_set": "base"}).json()
    figures = re.compile(r"€[\d,]+|\d+%|\d{1,2} \w{3} \d{4}")
    assert set(figures.findall(body["summary"])) <= set(figures.findall(" ".join(body["facts"])))


def test_without_a_plan_it_is_404(client: TestClient):
    assert client.post("/explain/projection", json={}).status_code == 404


class TestCompareSummary:
    def test_each_scenario_as_a_difference_from_the_plan(self, plan_client: TestClient):
        plan_client.post(
            "/scenarios",
            json={"name": "Spend €200 less", "overrides": {"monthly_expenses_delta": -200}},
        ).raise_for_status()
        body = plan_client.post("/explain/compare", json={}).json()
        facts = body["facts"]

        assert facts[0].startswith(
            "With the current plan, the €80,000 goal is reached on 1 Aug 2031"
        )
        assert "of 1,000 simulated futures it is reached by 1 Jun 2032" in facts[0]
        assert facts[1].startswith("Higher contribution: the goal is reached on")
        assert "than the current plan" in facts[1]
        income = next(f for f in facts if f.startswith("Higher income:"))
        assert "earlier)" in income
        assert "Spend €200 less reaches the goal earliest" in " ".join(facts)
        assert not any(word in body["summary"].lower() for word in ("should", "best", "recommend"))
        assert body["summary"] == " ".join(facts)

    def test_investing_more_with_a_lower_share_is_explained(self, plan_client: TestClient):
        facts = plan_client.post("/explain/compare", json={}).json()["facts"]
        compared = plan_client.post("/scenarios/compare/uncertainty", json={}).json()
        higher = next(s for s in compared["scenarios"] if s["name"] == "Higher contribution")
        explained = any("moves money from cash" in f for f in facts)
        assert explained == (higher["probability_difference"] < 0)
