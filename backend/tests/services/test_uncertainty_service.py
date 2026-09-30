"""The uncertainty simulation runs on the stored plan, at the profile's investment risk."""

from dataclasses import replace
from datetime import date

from sqlalchemy.orm import Session

from app.domain.models import InvestmentRisk
from app.domain.scenarios import Scenario, ScenarioOverrides
from app.domain.uncertainty import simulate_uncertainty
from app.services.profile import get_profile, save_profile
from app.services.uncertainty import simulate
from tests.sample_plan import BASE, GOAL, PROFILE, TODAY


def test_matches_the_domain_simulation_at_medium_risk(plan: Session):
    """The service only loads data and picks the volatility: the numbers are the engine's."""
    expected = simulate_uncertainty(
        Scenario("Current plan"), PROFILE, BASE, GOAL, date(2026, 10, 1), 0.10, paths=100
    )
    report = simulate(plan, TODAY, paths=100)
    assert report.result == expected
    assert report.investment_risk == InvestmentRisk.MEDIUM
    assert (report.scenario_name, report.assumption_set) == ("Current plan", "base")


def test_uses_the_saved_risk_level(plan: Session):
    save_profile(plan, replace(PROFILE, investment_risk=InvestmentRisk.HIGH))
    report = simulate(plan, TODAY, paths=100)
    assert report.investment_risk == InvestmentRisk.HIGH
    assert report.result.volatility == 0.15


def test_what_if_is_named_and_not_saved(plan: Session):
    drop = ScenarioOverrides(first_year_return=-0.30, annual_return=0.04)
    report = simulate(plan, TODAY, drop, paths=100)
    assert report.scenario_name == "What-if"
    assert report.assumptions.annual_return == 0.04
    assert get_profile(plan) == PROFILE


def test_the_seed_is_passed_through(plan: Session):
    assert simulate(plan, TODAY, paths=100, seed=7).result.seed == 7
    assert simulate(plan, TODAY, paths=100, seed=7) == simulate(plan, TODAY, paths=100, seed=7)
