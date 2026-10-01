"""/plan/draft over HTTP: a description in, a draft of the forms out, nothing saved."""

from fastapi.testclient import TestClient


def test_first_question_without_a_message(client: TestClient):
    body = client.post("/plan/draft", json={}).json()
    assert body["question"] == "How much do you take home each month, after tax?"
    assert body["still_missing"][0] == "Take-home pay"
    assert body["draft"]["asked"] == "monthly_net_income"
    assert not body["complete"]


def test_a_description_fills_the_draft_and_nothing_is_saved(client: TestClient):
    body = client.post(
        "/plan/draft",
        json={"message": "I take home 2,400 a month, spend 1,600 and want 60k for a house by 2032"},
    ).json()
    draft = body["draft"]
    assert (draft["monthly_net_income"], draft["monthly_expenses"]) == (2400, 1600)
    assert (draft["goal_target_amount"], draft["goal_target_date"]) == (60000, "2032-01-01")
    assert body["read_by"] == "rules"  # the tests use the mock provider
    assert "Take-home pay: €2,400 a month" in body["understood"]
    assert body["complete"]
    assert client.get("/profile").status_code == 404  # still nothing saved
    assert client.get("/goals").json() == []


def test_the_draft_goes_back_and_forth(client: TestClient):
    first = client.post("/plan/draft", json={"message": "I take home 2,400 a month"}).json()
    second = client.post("/plan/draft", json={"message": "1600", "draft": first["draft"]}).json()
    assert second["draft"]["monthly_net_income"] == 2400
    assert second["draft"]["monthly_expenses"] == 1600
    assert second["question"] == "How much do you want to save for your goal?"


def test_a_too_long_message_is_422(client: TestClient):
    response = client.post("/plan/draft", json={"message": "x" * 1001})
    assert response.status_code == 422
