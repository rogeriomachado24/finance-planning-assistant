"""Property-based tests: invariants that must hold for any valid input."""

import math
from dataclasses import replace
from datetime import date

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.domain.goals import calculate_required_monthly_contribution
from app.domain.models import Assumptions, FinancialProfile
from app.domain.projection import project
from app.domain.rates import annual_to_monthly_rate

START = date(2026, 10, 1)

amounts = st.floats(min_value=0, max_value=1_000_000, allow_nan=False, allow_infinity=False)
small_amounts = st.floats(min_value=0, max_value=20_000, allow_nan=False, allow_infinity=False)
returns = st.floats(min_value=0, max_value=0.15, allow_nan=False)
growth = st.floats(min_value=-0.05, max_value=0.10, allow_nan=False)
horizons = st.integers(min_value=1, max_value=600)


@st.composite
def profiles(draw) -> FinancialProfile:
    return FinancialProfile(
        monthly_net_income=draw(small_amounts),
        monthly_expenses=draw(small_amounts),
        cash=draw(amounts),
        investments=draw(amounts),
        monthly_investment_contribution=draw(small_amounts),
        other_monthly_income=draw(small_amounts),
        debt_balance=draw(amounts),
        monthly_debt_payment=draw(small_amounts),
    )


@st.composite
def assumption_sets(draw) -> Assumptions:
    return Assumptions(
        annual_return=draw(returns),
        annual_salary_growth=draw(growth),
        annual_expense_growth=draw(growth),
    )


def tolerance(value: float) -> float:
    return 1e-9 * max(1.0, abs(value))


@settings(max_examples=200)
@given(amounts, small_amounts, returns, horizons)
def test_simulator_matches_closed_form_when_surplus_covers_contribution(
    investments, contribution, annual_return, months
):
    profile = FinancialProfile(
        monthly_net_income=contribution,
        monthly_expenses=0,
        investments=investments,
        monthly_investment_contribution=contribution,
    )
    final = project(profile, Assumptions(annual_return=annual_return), START, months).at(months)
    # Reference computed from the definitions (lump sum growth + sum of each contribution's
    # growth), not the closed-form annuity formula, which is imprecise for tiny rates.
    r = annual_to_monthly_rate(annual_return)
    annuity = math.fsum((1 + r) ** k for k in range(months))
    expected = investments * (1 + r) ** months + contribution * annuity
    assert final.investments == pytest.approx(expected, rel=1e-9, abs=1e-6)


@settings(max_examples=200)
@given(profiles(), assumption_sets(), small_amounts, st.integers(min_value=1, max_value=240))
def test_higher_contribution_never_lowers_liquid_assets(profile, assumptions, extra, months):
    """Moving cash into investments can only help when returns are non-negative."""
    higher = replace(
        profile,
        monthly_investment_contribution=profile.monthly_investment_contribution + extra,
    )
    base = project(profile, assumptions, START, months).snapshots
    more = project(higher, assumptions, START, months).snapshots
    for b, m in zip(base, more, strict=True):
        assert m.liquid_assets >= b.liquid_assets - tolerance(b.liquid_assets)


@settings(max_examples=200)
@given(profiles(), assumption_sets(), returns, st.integers(min_value=1, max_value=240))
def test_higher_return_never_lowers_liquid_assets(profile, assumptions, other_return, months):
    low_return, high_return = sorted([assumptions.annual_return, other_return])
    low = project(profile, replace(assumptions, annual_return=low_return), START, months)
    high = project(profile, replace(assumptions, annual_return=high_return), START, months)
    for lo, hi in zip(low.snapshots, high.snapshots, strict=True):
        assert hi.liquid_assets >= lo.liquid_assets - tolerance(lo.liquid_assets)


@settings(max_examples=200)
@given(profiles(), growth, growth, st.integers(min_value=1, max_value=240))
def test_money_is_conserved_at_zero_return(profile, salary_growth, expense_growth, months):
    """With no investment return, liquid assets change by exactly the cumulative surplus."""
    assumptions = Assumptions(
        annual_salary_growth=salary_growth, annual_expense_growth=expense_growth
    )
    snapshots = project(profile, assumptions, START, months).snapshots
    cumulative_surplus = sum(s.surplus for s in snapshots)
    expected = profile.liquid_assets + cumulative_surplus
    assert snapshots[-1].liquid_assets == pytest.approx(expected, rel=1e-9, abs=1e-6)


@settings(max_examples=200)
@given(
    st.floats(min_value=1, max_value=2_000_000, allow_nan=False),
    horizons,
    amounts,
    amounts,
    returns,
)
def test_required_contribution_round_trip(target, months, cash, investments, annual_return):
    """Investing the required amount every month reaches the target on the target date."""
    required = calculate_required_monthly_contribution(
        target, months, cash, investments, annual_return
    )
    profile = FinancialProfile(
        monthly_net_income=required,
        monthly_expenses=0,
        cash=cash,
        investments=investments,
        monthly_investment_contribution=required,
    )
    final = project(profile, Assumptions(annual_return=annual_return), START, months).at(months)
    assert final.liquid_assets >= target - tolerance(target)
    if required > 0:
        assert final.liquid_assets == pytest.approx(target, rel=1e-9)
