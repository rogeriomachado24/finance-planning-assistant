"""`python -m app.seed`, run against a database that doesn't exist yet."""

import pytest

from app.config import Settings
from app.db.session import create_db_engine, create_session_factory
from app.seed import main
from app.services.assumptions import list_assumption_sets
from app.services.goals import list_goals
from app.services.plan_status import get_plan_status
from app.services.profile import get_profile


def goals_in(url: str) -> list[str]:
    engine = create_db_engine(url)
    try:
        with create_session_factory(engine)() as session:
            get_profile(session)  # raises if the profile is missing
            return [g.goal.name for g in list_goals(session)]
    finally:
        engine.dispose()


def test_seed_creates_and_fills_a_new_database(
    empty_db_url: str, capsys: pytest.CaptureFixture[str]
):
    assert main([], Settings(database_url=empty_db_url)) == 0
    assert goals_in(empty_db_url) == ["Buy a house"]
    output = capsys.readouterr().out
    assert "goal: Buy a house, 80,000 EUR by 1 Jun" in output
    assert "assumption sets: conservative, base, optimistic" in output


def test_seed_refuses_to_run_twice(empty_db_url: str, capsys: pytest.CaptureFixture[str]):
    settings = Settings(database_url=empty_db_url)
    main([], settings)
    assert main([], settings) == 1
    assert "Run with --reset" in capsys.readouterr().err


def test_reset_reloads_the_demo(empty_db_url: str):
    settings = Settings(database_url=empty_db_url)
    main([], settings)
    assert main(["--reset"], settings) == 0
    assert goals_in(empty_db_url) == ["Buy a house"]


def test_empty_removes_everything_but_the_assumption_presets(
    empty_db_url: str, capsys: pytest.CaptureFixture[str]
):
    settings = Settings(database_url=empty_db_url)
    main([], settings)  # the demo plan
    assert main(["--empty"], settings) == 0
    assert "no finances, no goal" in capsys.readouterr().out

    engine = create_db_engine(empty_db_url)
    try:
        with create_session_factory(engine)() as session:
            status = get_plan_status(session)
            assert (status.has_profile, status.has_goal) == (False, False)
            assert len(list_assumption_sets(session)) == 3
    finally:
        engine.dispose()


def test_empty_and_reset_cannot_be_combined(empty_db_url: str):
    with pytest.raises(SystemExit):
        main(["--empty", "--reset"], Settings(database_url=empty_db_url))
