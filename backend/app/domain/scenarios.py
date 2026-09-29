"""Scenario engine: named overrides applied to a base profile and assumptions.

The chat and the API both describe what-ifs with `ScenarioOverrides`, so
"what if I invest 200 more per month?" is simply
`ScenarioOverrides(monthly_investment_contribution_delta=200)`.
"""

from dataclasses import dataclass, field, replace
from datetime import date

from app.domain.cashflow import summarize_position
from app.domain.errors import InvalidInputError
from app.domain.goals import (
    calculate_required_monthly_contribution,
    find_goal_month,
    months_to_target_date,
)
from app.domain.models import Assumptions, FinancialProfile, Goal
from app.domain.projection import (
    MAX_PROJECTION_MONTHS,
    MonthSnapshot,
    ProjectionWarning,
    project,
)


@dataclass(frozen=True)
class ScenarioOverrides:
    """Changes relative to the saved plan. `None` means "keep the saved value"."""

    monthly_investment_contribution: float | None = None
    monthly_investment_contribution_delta: float | None = None
    monthly_net_income: float | None = None
    monthly_expenses: float | None = None
    annual_return: float | None = None
    annual_salary_growth: float | None = None
    annual_expense_growth: float | None = None

    def __post_init__(self) -> None:
        if (
            self.monthly_investment_contribution is not None
            and self.monthly_investment_contribution_delta is not None
        ):
            raise InvalidInputError(
                "set either monthly_investment_contribution or its delta, not both"
            )

    def apply(
        self, profile: FinancialProfile, assumptions: Assumptions
    ) -> tuple[FinancialProfile, Assumptions]:
        """Return the effective profile and assumptions. Validation re-runs on the results,
        so an override that produces an invalid value (e.g. a negative contribution) raises."""
        contribution = profile.monthly_investment_contribution
        if self.monthly_investment_contribution is not None:
            contribution = self.monthly_investment_contribution
        elif self.monthly_investment_contribution_delta is not None:
            contribution += self.monthly_investment_contribution_delta

        new_profile = replace(
            profile,
            monthly_investment_contribution=contribution,
            monthly_net_income=_keep(self.monthly_net_income, profile.monthly_net_income),
            monthly_expenses=_keep(self.monthly_expenses, profile.monthly_expenses),
        )
        new_assumptions = replace(
            assumptions,
            annual_return=_keep(self.annual_return, assumptions.annual_return),
            annual_salary_growth=_keep(self.annual_salary_growth, assumptions.annual_salary_growth),
            annual_expense_growth=_keep(
                self.annual_expense_growth, assumptions.annual_expense_growth
            ),
        )
        return new_profile, new_assumptions


def _keep[T](override: T | None, current: T) -> T:
    return current if override is None else override


@dataclass(frozen=True)
class Scenario:
    name: str
    overrides: ScenarioOverrides = field(default_factory=ScenarioOverrides)
    description: str = ""


@dataclass(frozen=True)
class ScenarioResult:
    scenario_name: str
    profile: FinancialProfile
    """Effective profile after overrides."""
    assumptions: Assumptions
    """Effective assumptions after overrides."""
    monthly_contribution: float
    monthly_surplus: float
    """Surplus in the first projected month (before any growth)."""
    target_amount: float
    target_date: date
    months_to_target_date: int
    projected_goal_date: date | None
    """None when the goal is not reached within the projection horizon."""
    months_to_goal: int | None
    projected_value_at_target_date: float
    reaches_goal: bool
    """Whether liquid assets reach the target by the target date."""
    shortfall: float
    required_monthly_contribution: float | None
    warnings: tuple[ProjectionWarning, ...]
    snapshots: tuple[MonthSnapshot, ...]
    """Monthly series up to the later of the target date and the goal date."""


def run_scenario(
    scenario: Scenario,
    profile: FinancialProfile,
    assumptions: Assumptions,
    goal: Goal,
    start: date,
    max_months: int = MAX_PROJECTION_MONTHS,
) -> ScenarioResult:
    months_to_target = months_to_target_date(goal.target_date, start, max_months)

    eff_profile, eff_assumptions = scenario.overrides.apply(profile, assumptions)
    projection = project(eff_profile, eff_assumptions, start, max_months)
    goal_month = find_goal_month(projection, goal.target_amount)
    value_at_target = projection.at(months_to_target).liquid_assets

    series_end = max(months_to_target, goal_month or 0)
    series = projection.snapshots[: series_end + 1]
    # Only report warnings that occur within the returned series.
    warnings = tuple(w for w in projection.warnings if w.month <= series_end)

    return ScenarioResult(
        scenario_name=scenario.name,
        profile=eff_profile,
        assumptions=eff_assumptions,
        monthly_contribution=eff_profile.monthly_investment_contribution,
        monthly_surplus=summarize_position(eff_profile).monthly_surplus,
        target_amount=goal.target_amount,
        target_date=goal.target_date,
        months_to_target_date=months_to_target,
        projected_goal_date=None if goal_month is None else projection.at(goal_month).date,
        months_to_goal=goal_month,
        projected_value_at_target_date=value_at_target,
        reaches_goal=value_at_target >= goal.target_amount,
        shortfall=max(goal.target_amount - value_at_target, 0.0),
        required_monthly_contribution=calculate_required_monthly_contribution(
            goal.target_amount,
            months_to_target,
            eff_profile.cash,
            eff_profile.investments,
            eff_assumptions.annual_return,
        ),
        warnings=warnings,
        snapshots=series,
    )


def compare_scenarios(
    scenarios: list[Scenario],
    profile: FinancialProfile,
    assumptions: Assumptions,
    goal: Goal,
    start: date,
) -> list[ScenarioResult]:
    return [run_scenario(s, profile, assumptions, goal, start) for s in scenarios]


def default_scenarios(
    assumptions: Assumptions,
    contribution_increase: float = 100.0,
    salary_growth_increase: float = 0.02,
) -> list[Scenario]:
    """The three Phase 1 scenarios: current plan, higher contribution, higher income."""
    base_growth = assumptions.annual_salary_growth
    higher_growth = base_growth + salary_growth_increase
    return [
        Scenario("Current plan", description="Your saved profile and assumptions."),
        Scenario(
            "Higher contribution",
            ScenarioOverrides(monthly_investment_contribution_delta=contribution_increase),
            description=f"Invest {contribution_increase:,.0f} EUR more per month.",
        ),
        Scenario(
            "Higher income",
            ScenarioOverrides(annual_salary_growth=higher_growth),
            description=(
                f"Salary grows {higher_growth:.1%} per year instead of {base_growth:.1%}."
            ),
        ),
    ]
