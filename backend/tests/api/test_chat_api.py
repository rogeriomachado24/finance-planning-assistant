"""POST /chat over HTTP, with the mock provider."""

from fastapi.testclient import TestClient


def test_a_conversation(plan_client: TestClient):
    first = plan_client.post("/chat", json={"message": "What if I invest €200 more per month?"})
    assert first.status_code == 200
    body = first.json()
    assert body["provider"] == "mock"
    assert body["status"] == "answered"
    assert body["intent"]["kind"] == "what_if"
    assert body["assumption_set"] == "base"
    assert body["assumptions"]["annual_return"] == 0.05
    assert [r["name"] for r in body["results"]] == ["Current plan", "What-if"]
    assert "This is a projection, not a guarantee." in body["reply"]

    follow_up = plan_client.post(
        "/chat", json={"message": "And with €300 instead?", "thread_id": body["thread_id"]}
    ).json()
    assert follow_up["thread_id"] == body["thread_id"]
    assert follow_up["results"][1]["result"]["monthly_contribution"] == 700


def test_the_requested_assumption_set_is_the_default(plan_client: TestClient):
    plan_client.put("/assumptions/optimistic", json={"annual_return": 0.07})
    body = plan_client.post(
        "/chat", json={"message": "Am I on track?", "assumption_set": "optimistic"}
    ).json()
    assert body["assumption_set"] == "optimistic"
    assert body["results"][0]["result"]["assumptions"]["annual_return"] == 0.07


def test_advice_is_declined(plan_client: TestClient):
    body = plan_client.post("/chat", json={"message": "Which ETF should I buy?"}).json()
    assert body["status"] == "declined"
    assert body["results"] == []


def test_without_a_plan_the_reply_says_what_is_missing(client: TestClient):
    body = client.post("/chat", json={"message": "Am I on track?"}).json()
    assert body["status"] == "clarification"
    assert "Your plan" in body["reply"]


def test_empty_message_is_422(client: TestClient):
    assert client.post("/chat", json={"message": "   "}).status_code == 422
