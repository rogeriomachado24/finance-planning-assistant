"""/health, /profile, /goals and /assumptions over HTTP."""

from dataclasses import fields

import pytest
from fastapi.testclient import TestClient

from app.domain.models import Assumptions, FinancialProfile
from app.schemas.plan import Profile, ProfileIn, Rates
from tests.api.conftest import BASE_JSON, GOAL_JSON, PROFILE_JSON


def test_health(client: TestClient):
    assert client.get("/health").json() == {"status": "ok", "database": "ok"}


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

    @pytest.mark.parametrize(
        "change",
        [
            {"cash": -1},
            {"monthly_expenses": 2_000_000_000},
            {"age": 150},
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
    def test_put_by_name_then_list(self, client: TestClient):
        client.put("/assumptions/base", json=BASE_JSON)
        client.put("/assumptions/optimistic", json=BASE_JSON | {"annual_return": 0.07})
        listed = client.get("/assumptions").json()
        assert [(s["name"], s["assumptions"]["annual_return"]) for s in listed] == [
            ("base", 0.05),
            ("optimistic", 0.07),
        ]

    def test_percent_instead_of_decimal_is_422(self, client: TestClient):
        response = client.put("/assumptions/base", json=BASE_JSON | {"annual_return": 7})
        assert response.status_code == 422
