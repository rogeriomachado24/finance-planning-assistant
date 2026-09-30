"""/simulate/uncertainty over HTTP."""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.domain.scenarios import Scenario
from app.domain.uncertainty import simulate_uncertainty
from tests.api.conftest import PROFILE_JSON
from tests.sample_plan import BASE, GOAL, PROFILE

FEW = {"paths": 200}


def test_returns_the_engine_result_rounded(plan_client: TestClient):
    expected = simulate_uncertainty(
        Scenario("Current plan"), PROFILE, BASE, GOAL, date(2026, 10, 1), 0.10, paths=200
    )
    body = plan_client.post("/simulate/uncertainty", json=FEW).json()
    assert body["investment_risk"] == "medium"
    assert body["volatility"] == 0.10
    assert (body["paths"], body["seed"]) == (200, 2026)
    assert body["probability_by_target_date"] == expected.probability_by_target_date
    assert body["value_at_target_date"]["p50"] == round(expected.value_at_target_date.p50, 2)
    assert body["goal_dates"]["p50"] == expected.goal_dates.p50.isoformat()
    assert len(body["bands"]) == expected.horizon_months + 1


def test_echoes_the_assumptions(plan_client: TestClient):
    body = plan_client.post("/simulate/uncertainty", json=FEW).json()
    assert body["assumption_set"] == "base"
    assert body["assumptions"]["annual_return"] == 0.05
    assert body["scenario_name"] == "Current plan"


def test_money_has_at_most_two_decimals(plan_client: TestClient):
    body = plan_client.post("/simulate/uncertainty", json=FEW).json()
    amounts = [b[p] for b in body["bands"] for p in ("p10", "p50", "p90")]
    assert all(round(v, 2) == v for v in amounts)


def test_the_saved_risk_level_is_used(plan_client: TestClient):
    plan_client.put("/profile", json=PROFILE_JSON | {"investment_risk": "low"})
    body = plan_client.post("/simulate/uncertainty", json=FEW).json()
    assert (body["investment_risk"], body["volatility"]) == ("low", 0.05)


def test_market_drop_what_if(plan_client: TestClient):
    plan = plan_client.post("/simulate/uncertainty", json=FEW).json()
    drop = plan_client.post(
        "/simulate/uncertainty", json=FEW | {"overrides": {"first_year_return": -0.3}}
    ).json()
    assert drop["scenario_name"] == "What-if"
    assert drop["probability_by_target_date"] < plan["probability_by_target_date"]


@pytest.mark.parametrize(
    "body",
    [
        {"paths": 0},
        {"paths": 10_001},
        {"seed": -1},
        {"volatility": 0.2},  # comes from the saved risk level, not the request
    ],
)
def test_invalid_request_is_422(plan_client: TestClient, body: dict):
    assert plan_client.post("/simulate/uncertainty", json=body).status_code == 422


def test_missing_plan_is_404(client: TestClient):
    assert client.post("/simulate/uncertainty", json=FEW).status_code == 404
