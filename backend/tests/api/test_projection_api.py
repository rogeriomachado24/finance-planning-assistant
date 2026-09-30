"""/simulate and /scenarios over HTTP."""

from dataclasses import fields
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.domain.scenarios import Scenario, ScenarioOverrides, run_scenario
from app.schemas.scenarios import OverridesIn, ScenarioResultOut
from tests.api.conftest import GOAL_JSON, PROFILE_JSON
from tests.sample_plan import BASE, GOAL, PROFILE

MORE_INVESTED = {"monthly_investment_contribution_delta": 200}


def test_override_schema_matches_the_domain():
    assert set(OverridesIn.model_fields) == {f.name for f in fields(ScenarioOverrides)}


class TestSimulate:
    def test_returns_the_engine_result_rounded_to_the_cent(self, plan_client: TestClient):
        expected = run_scenario(Scenario("Current plan"), PROFILE, BASE, GOAL, date(2026, 10, 1))
        response = plan_client.post("/simulate", json={})
        assert response.status_code == 200
        assert response.json() == ScenarioResultOut.from_domain(expected).model_dump(mode="json")

    def test_money_has_at_most_two_decimals(self, plan_client: TestClient):
        body = plan_client.post("/simulate", json={}).json()
        amounts = [v for s in body["snapshots"] for k, v in s.items() if k not in ("month", "date")]
        assert all(round(v, 2) == v for v in amounts)
        assert body["assumptions"] == {
            "annual_return": 0.05,
            "annual_salary_growth": 0.02,
            "annual_expense_growth": 0.02,
            "annual_inflation": 0.02,
        }

    def test_goal_progress_today(self, plan_client: TestClient):
        body = plan_client.post("/simulate", json={}).json()
        assert body["goal_progress"] == {
            "current_amount": 25000,
            "remaining": 55000,
            "fraction": 0.3125,
        }

    def test_what_if_is_not_saved(self, plan_client: TestClient):
        body = plan_client.post("/simulate", json={"overrides": MORE_INVESTED}).json()
        assert body["scenario_name"] == "What-if"
        assert body["monthly_contribution"] == 600
        assert (
            plan_client.get("/profile").json()["profile"]["monthly_investment_contribution"] == 400
        )

    def test_what_if_beyond_input_limits_still_returns(self, plan_client: TestClient):
        overrides = {"monthly_investment_contribution_delta": 1_000_000_000}
        response = plan_client.post("/simulate", json={"overrides": overrides})
        assert response.status_code == 200
        assert response.json()["warnings"][0]["code"] == "contribution_reduced"

    def test_missing_plan_is_404_with_a_message(self, client: TestClient):
        response = client.post("/simulate", json={})
        assert response.status_code == 404
        assert response.json()["detail"] == "no financial profile has been saved yet"

    def test_unknown_assumption_set_is_404(self, plan_client: TestClient):
        response = plan_client.post("/simulate", json={"assumption_set": "pessimistic"})
        assert response.status_code == 404

    @pytest.mark.parametrize(
        ("overrides", "detail"),
        [
            (
                {"monthly_investment_contribution": 500, **MORE_INVESTED},
                "set either monthly_investment_contribution or its delta, not both",
            ),
            (
                {"monthly_investment_contribution_delta": -1000},
                "monthly_investment_contribution must be >= 0; got -600.0",
            ),
        ],
    )
    def test_domain_rejections_are_422_with_a_message(
        self, plan_client: TestClient, overrides: dict, detail: str
    ):
        response = plan_client.post("/simulate", json={"overrides": overrides})
        assert response.status_code == 422
        assert response.json() == {"detail": detail}

    def test_unknown_override_is_422(self, plan_client: TestClient):
        response = plan_client.post("/simulate", json={"overrides": {"bonus": 5000}})
        assert response.status_code == 422

    def test_goal_date_in_the_past_is_rejected_when_saved(self, plan_client: TestClient):
        response = plan_client.post("/goals", json=GOAL_JSON | {"target_date": "2025-01-01"})
        assert response.status_code == 422
        assert "before the projection start" in response.json()["detail"]
        # the existing goal stays active, so projections keep working
        assert plan_client.post("/simulate", json={}).status_code == 200


class TestScenarios:
    def test_save_list_compare_delete(self, plan_client: TestClient):
        saved = plan_client.post(
            "/scenarios", json={"name": "Invest 200 more", "overrides": MORE_INVESTED}
        )
        assert saved.status_code == 201
        scenario_id = saved.json()["id"]
        assert [s["name"] for s in plan_client.get("/scenarios").json()] == ["Invest 200 more"]

        body = plan_client.post("/scenarios/compare", json={}).json()
        assert body["assumption_set"] == "base"
        assert body["baseline"] == "Current plan"
        assert [(s["name"], s["saved_id"]) for s in body["scenarios"]] == [
            ("Current plan", None),
            ("Higher contribution", None),
            ("Higher income", None),
            ("Invest 200 more", scenario_id),
        ]

        assert plan_client.delete(f"/scenarios/{scenario_id}").status_code == 204
        assert plan_client.get("/scenarios").json() == []
        assert plan_client.delete(f"/scenarios/{scenario_id}").status_code == 404

    def test_compare_given_scenarios_only(self, plan_client: TestClient):
        body = {"scenarios": [{"name": "Lower expenses", "overrides": {"monthly_expenses": 1500}}]}
        compared = plan_client.post("/scenarios/compare", json=body).json()["scenarios"]
        assert [s["name"] for s in compared] == ["Lower expenses"]
        assert compared[0]["result"]["monthly_surplus"] == 1000

    def test_differences_from_the_baseline_come_rounded_from_the_api(self, plan_client: TestClient):
        current, contribution, income = plan_client.post("/scenarios/compare", json={}).json()[
            "scenarios"
        ]
        assert current["vs_baseline"] == {"goal_months_earlier": 0, "value_at_target_difference": 0}
        assert income["vs_baseline"]["goal_months_earlier"] > 0
        difference = contribution["vs_baseline"]["value_at_target_difference"]
        assert difference > 0 and round(difference, 2) == difference

    def test_an_empty_scenario_list_is_422(self, plan_client: TestClient):
        assert plan_client.post("/scenarios/compare", json={"scenarios": []}).status_code == 422

    def test_built_in_name_is_422(self, plan_client: TestClient):
        response = plan_client.post("/scenarios", json={"name": "Current plan"})
        assert response.status_code == 422
        assert "built-in" in response.json()["detail"]


def test_profile_json_fixture_is_complete():
    """Guards the fixtures: the sample profile sent over HTTP has every field."""
    assert set(PROFILE_JSON) == {f.name for f in fields(PROFILE)}
