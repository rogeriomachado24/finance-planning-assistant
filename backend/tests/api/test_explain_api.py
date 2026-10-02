"""'What does this mean for me?' over HTTP, with the mock provider: the facts come from the
engine as labelled points, and the summary is the facts themselves (no model)."""

import re

from fastapi.testclient import TestClient

from tests.api.conftest import GOAL_JSON, PROFILE_JSON


def points_of(body: dict) -> dict[str, str]:
    return {p["label"]: p["text"] for p in body["points"]}


def test_projection_summary_from_the_engine(plan_client: TestClient):
    body = plan_client.post("/explain/projection", json={}).json()
    projection = plan_client.post("/simulate", json={}).json()
    futures = plan_client.post("/simulate/uncertainty", json={}).json()
    points = points_of(body)

    assert list(points) == [
        "Goal (€80,000 by 1 Jun 2032)",
        "Simulated futures",
        "To be on time in 9 of 10",
    ]
    assert points["Goal (€80,000 by 1 Jun 2032)"] == (
        "under these assumptions, reached on 1 Aug 2031, 10 months early."
    )
    assert points["Simulated futures"].startswith("on time in about ")
    assert points["Simulated futures"].endswith(" of 1,000.")
    nine = next(x for x in futures["required_monthly_investment"] if x["share"] == 0.9)
    assert points["To be on time in 9 of 10"] == (
        f"about €{round(nine['monthly_amount']):,} a month would need to be invested "
        f"(today €{round(projection['monthly_contribution']):,})."
    )
    # The same facts as sentences, and (without a model) the summary is those sentences
    assert body["facts"] == [f"{label}: {text}" for label, text in points.items()]
    assert body["summary"] == " ".join(body["facts"])
    assert body["worded_by"] == "template"


def test_a_plan_behind_target_says_how_short(plan_client: TestClient):
    plan_client.post("/goals", json=GOAL_JSON | {"target_amount": 120_000}).raise_for_status()
    points = points_of(plan_client.post("/explain/projection", json={}).json())
    goal = points["Goal (€120,000 by 1 Jun 2032)"]
    assert goal.startswith("under these assumptions, not reached: €")
    assert "short; reached on" in goal
    assert points["When it's missed"].startswith("typically €")


def test_a_goal_already_covered_needs_no_more_facts(plan_client: TestClient):
    plan_client.put("/profile", json=PROFILE_JSON | {"cash": 90_000}).raise_for_status()
    body = plan_client.post("/explain/projection", json={}).json()
    assert body["points"] == [
        {
            "label": "Goal (€80,000 by 1 Jun 2032)",
            "text": "already covered by today's cash and investments.",
        }
    ]


def test_money_kept_aside_is_a_fact(plan_client: TestClient):
    keep = {"keep_savings": 5000, "keep_investments": 7000}
    plan_client.post("/goals", json=GOAL_JSON | keep).raise_for_status()
    kept = plan_client.post("/simulate", json={}).json()["kept_aside"]
    points = points_of(plan_client.post("/explain/projection", json={}).json())
    assert list(points)[1] == "Kept aside"
    assert points["Kept aside"] == (
        "€5,000 of savings and €7,000 of investments not counted for this goal; "
        f"about €{round(kept['total_at_target']):,} by the target date."
    )


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
        points = points_of(body)

        assert list(points)[:4] == [
            "Current plan",
            "Higher contribution",
            "Higher income",
            "Spend €200 less",
        ]
        assert points["Current plan"].startswith(
            "€80,000 reached on 1 Aug 2031; on time (1 Jun 2032)"
        )
        assert points["Current plan"].endswith(" of 1,000 simulated futures.")
        assert points["Higher income"].startswith(
            "reached on 1 Apr 2031 (4 months earlier); on time"
        )
        assert points["Earliest"] == "Spend €200 less, on 1 Nov 2030."
        assert not any(word in body["summary"].lower() for word in ("should", "best", "recommend"))

    def test_investing_more_with_a_lower_share_is_explained(self, plan_client: TestClient):
        points = points_of(plan_client.post("/explain/compare", json={}).json())
        compared = plan_client.post("/scenarios/compare/uncertainty", json={}).json()
        higher = next(s for s in compared["scenarios"] if s["name"] == "Higher contribution")
        explained = "moves money from cash" in points.get("Note", "")
        assert explained == (higher["probability_difference"] < 0)
