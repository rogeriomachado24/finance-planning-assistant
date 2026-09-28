from collections.abc import Iterator
from dataclasses import asdict

import pytest
from fastapi.encoders import jsonable_encoder
from fastapi.testclient import TestClient

from app.api.deps import get_today
from app.config import Settings
from app.main import create_app
from tests.sample_plan import BASE, GOAL, PROFILE, TODAY

PROFILE_JSON = asdict(PROFILE)
BASE_JSON = asdict(BASE)
GOAL_JSON = jsonable_encoder(asdict(GOAL))


@pytest.fixture
def client(db_url: str) -> Iterator[TestClient]:
    """The real app on an empty, migrated database, with the clock fixed to TODAY."""
    app = create_app(Settings(database_url=db_url))
    app.dependency_overrides[get_today] = lambda: TODAY
    with TestClient(app) as client:
        yield client


@pytest.fixture
def plan_client(client: TestClient) -> TestClient:
    """The sample plan, stored through the API itself."""
    client.put("/profile", json=PROFILE_JSON).raise_for_status()
    client.put("/assumptions/base", json=BASE_JSON).raise_for_status()
    client.post("/goals", json=GOAL_JSON).raise_for_status()
    return client
