import math
import random
import statistics
import time
from dataclasses import replace
from datetime import date

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.domain.errors import InvalidInputError
from app.domain.models import Assumptions, FinancialProfile
from app.domain.projection import project
from app.domain.scenarios import Scenario, ScenarioOverrides, run_scenario
from app.domain.uncertainty import (
    DEFAULT_SEED,
    MONTHS_AFTER_TARGET,
    Percentiles,
    compare_uncertainty,
    percentile,
    probability_difference,
    sample_yearly_returns,
    simulate_uncertainty,
)

PLAN = Scenario("Current plan")


def simulate(profile, assumptions, goal, start, volatility=0.10, scenario=PLAN, **kwargs):
    return simulate_uncertainty(scenario, profile, assumptions, goal, start, volatility, **kwargs)


class TestSampler:
    def test_log_returns_have_the_chosen_mean_and_spread(self):
        """With 20,000 draws the sample mean is within 4 standard errors of ln(1.05)."""
        returns = sample_yearly_returns(random.Random(1), 0.05, 0.10, 20_000)
        logs = [math.log1p(r) for r in returns]
        assert statistics.fmean(logs) == pytest.approx(math.log1p(0.05), abs=4 * 0.10 / 141)
        assert statistics.stdev(logs) == pytest.approx(0.10, rel=0.03)

    def test_no_year_loses_everything(self):
        returns = sample_yearly_returns(random.Random(1), 0.05, 1.0, 10_000)
        assert min(returns) > -1

    def test_zero_volatility_gives_the_typical_return(self):
        assert sample_yearly_returns(random.Random(1), 0.05, 0, 3) == pytest.approx([0.05] * 3)


class TestPercentile:
    VALUES = [float(v) for v in range(1, 11)]  # 1..10

    @pytest.mark.parametrize(("p", "expected"), [(0, 1), (10, 1), (15, 2), (50, 5), (90, 9)])
    def test_nearest_rank(self, p, expected):
        assert percentile(self.VALUES, p) == expected

    def test_hundredth_is_the_maximum(self):
        assert percentile(self.VALUES, 100) == 10

    def test_rejects_an_empty_list(self):
        with pytest.raises(InvalidInputError):
            percentile([], 50)

    @given(st.lists(st.floats(-1e9, 1e9), min_size=1, max_size=200))
    def test_percentiles_are_ordered_and_within_range(self, values):
        p = Percentiles.of(values)
        assert min(values) <= p.p10 <= p.p50 <= p.p90 <= max(values)


class TestWithoutVolatility:
    """With no volatility every future is the Phase 1 projection."""

    def test_every_future_equals_the_projection(self, profile, assumptions, goal, start):
        result = simulate(profile, assumptions, goal, start, volatility=0, paths=20)
        projection = project(profile, assumptions, start, result.horizon_months)
        for point in result.bands:
            expected = projection.at(point.month).liquid_assets
            assert point.p10 == point.p50 == point.p90 == pytest.approx(expected)

    def test_probability_matches_reaches_goal(self, profile, assumptions, goal, start):
        for target in (80_000, 150_000):
            g = replace(goal, target_amount=target)
            deterministic = run_scenario(PLAN, profile, assumptions, g, start)
            result = simulate(profile, assumptions, g, start, volatility=0, paths=20)
            assert result.probability_by_target_date == (1.0 if deterministic.reaches_goal else 0)

    def test_goal_date_matches_the_projection(self, profile, assumptions, goal, start):
        deterministic = run_scenario(PLAN, profile, assumptions, goal, start)
        dates = simulate(profile, assumptions, goal, start, volatility=0, paths=20).goal_dates
        assert dates.p10 == dates.p50 == dates.p90 == deterministic.projected_goal_date

    def test_market_drop_matches_the_deterministic_what_if(self, profile, assumptions, goal, start):
        drop = Scenario("Drop", ScenarioOverrides(first_year_return=-0.30))
        deterministic = run_scenario(drop, profile, assumptions, goal, start)
        result = simulate(profile, assumptions, goal, start, volatility=0, scenario=drop, paths=5)
        assert result.value_at_target_date.p50 == pytest.approx(
            deterministic.projected_value_at_target_date
        )


class TestMedianIsThePhase1Line:
    def test_investments_alone(self, assumptions, goal, start):
        """No contributions: the median future compounds at exactly the assumed return."""
        profile = FinancialProfile(monthly_net_income=0, monthly_expenses=0, investments=50_000)
        result = simulate(profile, assumptions, goal, start)
        expected = project(profile, assumptions, start, 68).at(68).liquid_assets
        assert result.value_at_target_date.p50 == pytest.approx(expected, rel=0.03)

    def test_full_plan(self, profile, assumptions, goal, start):
        deterministic = run_scenario(PLAN, profile, assumptions, goal, start)
        result = simulate(profile, assumptions, goal, start)
        assert result.value_at_target_date.p50 == pytest.approx(
            deterministic.projected_value_at_target_date, rel=0.02
        )


class TestSummary:
    @pytest.fixture
    def result(self, profile, assumptions, goal, start):
        return simulate(profile, assumptions, goal, start)

    def test_echoes_the_inputs(self, result, goal):
        assert (result.paths, result.seed, result.volatility) == (1000, DEFAULT_SEED, 0.10)
        assert result.target_amount == goal.target_amount
        assert result.target_date == goal.target_date
        assert result.months_to_target_date == 68

    def test_runs_ten_years_past_the_target_date(self, result):
        assert result.horizon_months == 68 + MONTHS_AFTER_TARGET
        assert len(result.bands) == result.horizon_months + 1
        assert result.bands[0].date == date(2026, 10, 1)

    def test_starts_from_today_in_every_future(self, result):
        assert result.bands[0].p10 == result.bands[0].p90 == 25_000

    def test_margin_formula(self, result):
        p = result.probability_by_target_date
        assert 0 < p < 1
        assert result.probability_margin == pytest.approx(1.96 * math.sqrt(p * (1 - p) / 1000))

    def test_bands_are_ordered(self, result):
        assert all(b.p10 <= b.p50 <= b.p90 for b in result.bands)

    def test_goal_dates_are_ordered(self, result):
        dates = result.goal_dates
        assert dates.p10 <= dates.p50 <= dates.p90

    def test_reached_by_rises_over_time(self, result, goal):
        shares = [r.share for r in result.reached_by]
        assert shares == sorted(shares)
        assert all(r.date.month == 1 or r.date == goal.target_date for r in result.reached_by)

    def test_reached_by_the_target_date_includes_the_probability(self, result, goal):
        """Reaching the target once counts even if a later fall dips below it again."""
        by_target = next(r.share for r in result.reached_by if r.date == goal.target_date)
        assert by_target >= result.probability_by_target_date

    def test_shortfall_is_measured_in_the_futures_that_miss(self, result):
        shortfall = result.shortfall_when_missed
        assert shortfall is not None
        assert 0 < shortfall.p10 <= shortfall.p50 <= shortfall.p90

    def test_no_shortfall_when_every_future_reaches_the_goal(
        self, profile, assumptions, goal, start
    ):
        easy = replace(goal, target_amount=30_000)
        result = simulate(profile, assumptions, easy, start, paths=200)
        assert result.probability_by_target_date == 1
        assert result.shortfall_when_missed is None
        assert result.probability_margin == 0

    def test_futures_that_never_reach_the_goal(self, profile, assumptions, goal, start):
        impossible = replace(goal, target_amount=10_000_000)
        result = simulate(profile, assumptions, impossible, start, paths=50)
        assert result.not_reached_share == 1
        assert result.goal_dates.p10 is None


class TestReproducibility:
    def test_same_seed_same_result(self, profile, assumptions, goal, start):
        first = simulate(profile, assumptions, goal, start, paths=200, seed=7)
        assert simulate(profile, assumptions, goal, start, paths=200, seed=7) == first

    def test_different_seeds_agree_within_a_few_points(self, profile, assumptions, goal, start):
        probabilities = [
            simulate(profile, assumptions, goal, start, seed=seed).probability_by_target_date
            for seed in (1, 2)
        ]
        assert abs(probabilities[0] - probabilities[1]) < 0.04


class TestSameRandomDrawsAcrossScenarios:
    """Every scenario sees the same futures, so differences come from the plan, not luck."""

    @pytest.mark.parametrize(
        "better",
        [
            ScenarioOverrides(annual_return=0.06),
            ScenarioOverrides(monthly_net_income_delta=100),
            ScenarioOverrides(
                monthly_net_income_delta=100, monthly_investment_contribution_delta=100
            ),
        ],
    )
    def test_more_money_or_a_higher_return_never_lowers_any_future(
        self, profile, assumptions, goal, start, better
    ):
        base = simulate(profile, assumptions, goal, start, paths=300)
        improved = simulate(
            profile, assumptions, goal, start, scenario=Scenario("Better", better), paths=300
        )
        assert improved.probability_by_target_date >= base.probability_by_target_date
        for before, after in zip(base.bands, improved.bands, strict=True):
            assert after.p10 >= before.p10
            assert after.p50 >= before.p50
            assert after.p90 >= before.p90

    def test_investing_cash_raises_the_typical_future_but_widens_the_range(
        self, profile, assumptions, goal, start
    ):
        """Moving €100 a month from cash (safe, earns nothing) to investments (grow at 5% in a
        typical year, can fall) raises the middle and the top of the range, not the bottom."""
        invest_more = Scenario(
            "Invest more", ScenarioOverrides(monthly_investment_contribution_delta=100)
        )
        base = simulate(profile, assumptions, goal, start, paths=300).value_at_target_date
        more = simulate(
            profile, assumptions, goal, start, scenario=invest_more, paths=300
        ).value_at_target_date
        assert more.p50 > base.p50
        assert more.p90 > base.p90
        assert more.p90 - more.p10 > base.p90 - base.p10

    def test_a_market_drop_lowers_the_probability(self, profile, assumptions, goal, start):
        drop = Scenario("Drop", ScenarioOverrides(first_year_return=-0.30))
        base = simulate(profile, assumptions, goal, start, paths=300)
        result = simulate(profile, assumptions, goal, start, scenario=drop, paths=300)
        assert result.probability_by_target_date < base.probability_by_target_date


class TestInputs:
    @pytest.mark.parametrize("volatility", [-0.01, 1.01])
    def test_rejects_volatility_out_of_range(self, profile, assumptions, goal, start, volatility):
        with pytest.raises(InvalidInputError):
            simulate(profile, assumptions, goal, start, volatility=volatility)

    @pytest.mark.parametrize("paths", [0, 10_001])
    def test_rejects_paths_out_of_range(self, profile, assumptions, goal, start, paths):
        with pytest.raises(InvalidInputError):
            simulate(profile, assumptions, goal, start, paths=paths)

    def test_extreme_volatility_does_not_crash(self, profile, assumptions, goal, start):
        """At 100% volatility some years return more than +100%, which the rate check for
        typed-in assumptions would reject."""
        result = simulate(profile, assumptions, goal, start, volatility=1.0, paths=100)
        assert 0 <= result.probability_by_target_date <= 1

    def test_fifty_year_goal_stays_fast(self, profile, assumptions, goal, start):
        """The horizon is capped at 50 years; 1,000 futures take a few seconds at most."""
        far = replace(goal, target_amount=2_000_000, target_date=date(2076, 10, 1))
        began = time.perf_counter()
        result = simulate(profile, Assumptions(annual_return=0.05), far, start)
        assert result.horizon_months == 600
        assert time.perf_counter() - began < 15


class TestCompareUncertainty:
    def test_each_scenario_equals_its_own_simulation_on_the_same_seed(
        self, profile, assumptions, goal, start
    ):
        scenarios = [PLAN, Scenario("Drop", ScenarioOverrides(first_year_return=-0.30))]
        results = compare_uncertainty(
            scenarios, profile, assumptions, goal, start, 0.10, paths=100, seed=5
        )
        assert results == [
            simulate(profile, assumptions, goal, start, scenario=s, paths=100, seed=5)
            for s in scenarios
        ]

    def test_probability_difference_from_the_baseline(self, profile, assumptions, goal, start):
        more = Scenario("More income", ScenarioOverrides(monthly_net_income_delta=300))
        base, better = compare_uncertainty(
            [PLAN, more], profile, assumptions, goal, start, 0.10, paths=200
        )
        difference = probability_difference(better, base)
        assert difference == better.probability_by_target_date - base.probability_by_target_date
        assert difference >= 0
        assert probability_difference(base, base) == 0
