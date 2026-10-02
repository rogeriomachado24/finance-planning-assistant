"""/health, /profile, /goals and /assumptions over HTTP."""

from dataclasses import fields

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.domain.models import Assumptions, FinancialProfile
from app.main import create_app
from app.schemas.plan import Profile, ProfileIn, Rates
from tests.api.conftest import BASE_JSON, GOAL_JSON, PROFILE_JSON


def test_health(client: TestClient):
    assert client.get("/health").json() == {
        "status": "ok",
        "database": "ok",
        "llm": {"provider": "mock", "available": True},
    }


def test_interactive_docs_are_served(client: TestClient):
    assert client.get("/docs").status_code == 200
    assert "/simulate" in client.get("/openapi.json").json()["paths"]


@pytest.mark.parametrize(
    ("schema", "dataclass"),
    [(ProfileIn, FinancialProfile), (Profile, FinancialProfile), (Rates, Assumptions)],
)
def test_schemas_have_the_same_fields_as_the_domain(schema, dataclass):
    assert set(schema.model_fields) == {f.name for f in fields(dataclass)}


class TestProfile:
    def test_missing_profile_is_404_with_a_message(self, client: TestClient):
        response = client.get("/profile")
        assert response.status_code == 404
        assert response.json() == {"detail": "no financial profile has been saved yet"}

    def test_put_then_get(self, client: TestClient):
        assert client.put("/profile", json=PROFILE_JSON).status_code == 200
        body = client.get("/profile").json()
        assert body["profile"]["cash"] == 10_000
        assert body["position"] == {
            "total_monthly_income": 2500.0,
            "monthly_expenses": 1700.0,
            "monthly_debt_payment": 0.0,
            "monthly_surplus": 800.0,
            "savings_rate": 0.32,
            "liquid_assets": 25_000.0,
            "net_worth": 25_000.0,
        }

    def test_only_income_and_expenses_are_required(self, client: TestClient):
        body = client.put("/profile", json={"monthly_net_income": 2000, "monthly_expenses": 1500})
        assert body.json()["profile"]["cash"] == 0
        assert body.json()["profile"]["investment_risk"] == "medium"

    def test_investment_risk_is_saved(self, client: TestClient):
        client.put("/profile", json=PROFILE_JSON | {"investment_risk": "high"})
        assert client.get("/profile").json()["profile"]["investment_risk"] == "high"

    @pytest.mark.parametrize(
        "change",
        [
            {"cash": -1},
            {"monthly_expenses": 2_000_000_000},
            {"age": 150},
            {"investment_risk": "extreme"},
            {"salary": 3000},  # unknown field: probably a typo, so rejected
        ],
    )
    def test_invalid_profile_is_422(self, client: TestClient, change: dict):
        response = client.put("/profile", json=PROFILE_JSON | change)
        assert response.status_code == 422


class TestGoals:
    def test_new_goal_becomes_active(self, client: TestClient):
        first = client.post("/goals", json=GOAL_JSON)
        assert first.status_code == 201
        car = {"name": "Buy a car", "target_amount": 15_000, "target_date": "2028-01-01"}
        second = client.post("/goals", json=car).json()

        listed = client.get("/goals").json()
        assert [(g["name"], g["is_active"]) for g in listed] == [
            ("Buy a car", True),
            ("Buy a house", False),
        ]
        assert second["goal_type"] == "other"

    @pytest.mark.parametrize(
        "change",
        [{"target_amount": 0}, {"goal_type": "yacht"}, {"name": "   "}, {"target_date": "soon"}],
    )
    def test_invalid_goal_is_422(self, client: TestClient, change: dict):
        assert client.post("/goals", json=GOAL_JSON | change).status_code == 422


class TestAssumptions:
    def test_presets_are_there_from_the_first_start(self, client: TestClient):
        listed = client.get("/assumptions").json()
        assert [(s["name"], s["assumptions"]["annual_return"]) for s in listed] == [
            ("conservative", 0.02),
            ("base", 0.05),
            ("optimistic", 0.07),
        ]

    def test_put_replaces_by_name_or_adds(self, client: TestClient):
        client.put("/assumptions/base", json=BASE_JSON | {"annual_return": 0.045})
        client.put("/assumptions/my-own", json=BASE_JSON | {"annual_return": 0.06})
        listed = client.get("/assumptions").json()
        assert [(s["name"], s["assumptions"]["annual_return"]) for s in listed] == [
            ("conservative", 0.02),
            ("base", 0.045),
            ("optimistic", 0.07),
            ("my-own", 0.06),
        ]

    def test_percent_instead_of_decimal_is_422(self, client: TestClient):
        response = client.put("/assumptions/base", json=BASE_JSON | {"annual_return": 7})
        assert response.status_code == 422


def test_startup_builds_a_database_that_does_not_exist_yet(empty_db_url: str):
    app = create_app(Settings(database_url=empty_db_url))
    with TestClient(app) as client:
        assert client.get("/health").json()["database"] == "ok"
        assert len(client.get("/assumptions").json()) == 3
        assert client.get("/profile").status_code == 404  # no demo data unless asked for


class TestPlanStatus:
    def test_follows_the_setup_steps(self, client: TestClient):
        def status() -> dict:
            return client.get("/plan/status").json()

        assert status() == {"has_profile": False, "has_goal": False, "ready": False}
        client.put("/profile", json=PROFILE_JSON)
        assert status() == {"has_profile": True, "has_goal": False, "ready": False}
        client.post("/goals", json=GOAL_JSON)
        assert status() == {"has_profile": True, "has_goal": True, "ready": True}


class TestStartFresh:
    def test_clears_the_plan_but_keeps_the_assumption_sets(self, client: TestClient):
        client.put("/profile", json=PROFILE_JSON).raise_for_status()
        client.post("/goals", json=GOAL_JSON).raise_for_status()
        client.post("/scenarios", json={"name": "Spend less", "overrides": {}}).raise_for_status()
        sets_before = client.get("/assumptions").json()

        assert client.delete("/plan").status_code == 204

        assert client.get("/profile").status_code == 404
        assert client.get("/goals").json() == []
        assert client.get("/scenarios").json() == []
        assert client.get("/assumptions").json() == sets_before
        assert client.get("/plan/status").json() == {
            "has_profile": False,
            "has_goal": False,
            "ready": False,
        }

    def test_clearing_an_empty_plan_is_fine(self, client: TestClient):
        assert client.delete("/plan").status_code == 204


class TestKeptAside:
    def test_a_goal_keeps_money_aside_and_the_projection_counts_the_rest(self, client):
        client.put("/profile", json=PROFILE_JSON).raise_for_status()  # €10,000 + €15,000
        client.put("/assumptions/base", json=BASE_JSON).raise_for_status()
        keep = {"keep_savings": 5000, "keep_investments": 7000}
        goal = client.post("/goals", json=GOAL_JSON | keep).json()
        assert (goal["keep_savings"], goal["keep_investments"]) == (5000, 7000)

        result = client.post("/simulate", json={}).json()
        today = result["snapshots"][0]
        assert (today["kept_savings"], today["kept_investments"]) == (5000, 7000)
        assert today["counted"] == 13_000  # 25,000 - 12,000 kept aside
        assert result["goal_progress"]["current_amount"] == 13_000

    def test_kept_amounts_must_not_be_negative(self, client):
        response = client.post("/goals", json=GOAL_JSON | {"keep_savings": -1})
        assert response.status_code == 422
