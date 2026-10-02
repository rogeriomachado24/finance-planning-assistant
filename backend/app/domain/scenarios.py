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
    GoalProgress,
    calculate_goal_progress,
    calculate_required_monthly_contribution,
    find_goal_month,
    months_to_target_date,
)
from app.domain.models import NOTHING_KEPT, Assumptions, FinancialProfile, Goal, KeptAside
from app.domain.projection import (
    MAX_PROJECTION_MONTHS,
    MonthSnapshot,
    ProjectionWarning,
    project,
)
from app.domain.rates import validate_annual_rate


@dataclass(frozen=True)
class ScenarioOverrides:
    """Changes relative to the saved plan. `None` means "keep the saved value".

    Monthly amounts can be set to a new value or changed by a delta ("spend 200 less" is
    `monthly_expenses_delta=-200`), so callers such as the chat never do the arithmetic.
    """

    monthly_investment_contribution: float | None = None
    monthly_investment_contribution_delta: float | None = None
    monthly_net_income: float | None = None
    monthly_net_income_delta: float | None = None
    monthly_expenses: float | None = None
    monthly_expenses_delta: float | None = None
    annual_return: float | None = None
    annual_salary_growth: float | None = None
    annual_expense_growth: float | None = None
    first_year_return: float | None = None
    """Return of the first projected year only, e.g. -0.30 for "markets fall 30% next year";
    later years use the assumed return again."""
    keep_savings: float | None = None
    """Savings the goal doesn't use, instead of the goal's own amount."""
    keep_investments: float | None = None
    """Today's investments the goal doesn't use, instead of the goal's own amount."""
    keep_all_savings: bool | None = None
    """"Don't touch my savings": keep all of today's cash aside (copied from the profile)."""
    keep_all_investments: bool | None = None
    """"Don't touch my investments": keep all of today's investments aside."""

    def __post_init__(self) -> None:
        if self.first_year_return is not None:
            validate_annual_rate(self.first_year_return, "first_year_return")
        for name in ("keep_savings", "keep_investments"):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise InvalidInputError(f"{name} must be >= 0; got {value}")
        for name in _AMOUNTS_WITH_DELTA:
            if getattr(self, name) is not None and getattr(self, f"{name}_delta") is not None:
                raise InvalidInputError(f"set either {name} or its delta, not both")

    def apply(
        self, profile: FinancialProfile, assumptions: Assumptions
    ) -> tuple[FinancialProfile, Assumptions]:
        """Return the effective profile and assumptions. Validation re-runs on the results,
        so an override that produces an invalid value (e.g. a negative contribution) raises."""
        new_profile = replace(
            profile,
            **{name: self._amount(name, getattr(profile, name)) for name in _AMOUNTS_WITH_DELTA},
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

    def kept_aside(self, goal: Goal, profile: FinancialProfile) -> KeptAside:
        """What the goal keeps aside under this what-if: the override, or "all of today's"
        (the profile's amount, copied), or else the goal's own amount."""
        savings = profile.cash if self.keep_all_savings else self.keep_savings
        investments = profile.investments if self.keep_all_investments else self.keep_investments
        return KeptAside(
            savings=_keep(savings, goal.keep_savings),
            investments=_keep(investments, goal.keep_investments),
        )

    def yearly_returns(self, assumptions: Assumptions, years: int) -> list[float] | None:
        """The return of each projected year, or None when every year uses the assumption."""
        if self.first_year_return is None:
            return None
        return [self.first_year_return] + [assumptions.annual_return] * (years - 1)

    def _amount(self, name: str, current: float) -> float:
        absolute, delta = getattr(self, name), getattr(self, f"{name}_delta")
        if absolute is not None:
            return absolute
        return current if delta is None else current + delta


_AMOUNTS_WITH_DELTA = ("monthly_investment_contribution", "monthly_net_income", "monthly_expenses")


def _keep[T](override: T | None, current: T) -> T:
    return current if override is None else override


@dataclass(frozen=True)
class Scenario:
    name: str
    overrides: ScenarioOverrides = field(default_factory=ScenarioOverrides)
    description: str = ""


@dataclass(frozen=True)
class KeptAsideView:
    """The money a goal keeps aside, today and on the target date (docs/KEPT_ASIDE_DESIGN.md):
    kept savings stay the amount kept; kept investments grow with the portfolio."""

    savings_today: float
    investments_today: float
    total_today: float
    savings_at_target: float
    investments_at_target: float
    investment_growth: float
    """Growth of the kept investments by the target date (negative if they fell)."""
    total_at_target: float
    liquid_at_target: float
    """Cash + investments altogether on the target date: counted + kept aside."""

    @classmethod
    def of(cls, today: MonthSnapshot, at_target: MonthSnapshot) -> "KeptAsideView":
        return cls(
            savings_today=today.kept_savings,
            investments_today=today.kept_investments,
            total_today=today.kept_aside,
            savings_at_target=at_target.kept_savings,
            investments_at_target=at_target.kept_investments,
            investment_growth=at_target.kept_investments - today.kept_investments,
            total_at_target=at_target.kept_aside,
            liquid_at_target=at_target.liquid_assets,
        )


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
    """What counts towards the goal on the target date: cash + investments minus what the
    goal keeps aside."""
    reaches_goal: bool
    """Whether liquid assets reach the target by the target date."""
    shortfall: float
    required_monthly_contribution: float | None
    goal_progress: GoalProgress
    """How far today's counted amount (cash + investments minus what is kept aside) already
    is towards the target."""
    kept_aside: KeptAsideView | None
    """What the goal keeps aside, today and on the target date; None when nothing is."""
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
    yearly_returns = scenario.overrides.yearly_returns(eff_assumptions, -(-max_months // 12))
    kept = scenario.overrides.kept_aside(goal, eff_profile)
    projection = project(
        eff_profile, eff_assumptions, start, max_months, yearly_returns, kept_aside=kept
    )
    goal_month = find_goal_month(projection, goal.target_amount)
    value_at_target = projection.at(months_to_target).counted

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
            yearly_returns,
            kept_aside=kept,
        ),
        goal_progress=calculate_goal_progress(projection.at(0).counted, goal.target_amount),
        kept_aside=(
            KeptAsideView.of(projection.at(0), projection.at(months_to_target))
            if kept != NOTHING_KEPT
            else None
        ),
        warnings=warnings,
        snapshots=series,
    )


@dataclass(frozen=True)
class ScenarioDelta:
    """How a scenario's outcome differs from a baseline scenario (usually the current plan)."""

    goal_months_earlier: int | None
    """Months earlier (positive) or later (negative) that the goal is reached. None when
    either scenario doesn't reach it within the projection horizon."""
    value_at_target_difference: float
    """Liquid assets on the target date, minus the baseline's."""


def delta_from_baseline(result: ScenarioResult, baseline: ScenarioResult) -> ScenarioDelta:
    earlier = None
    if result.months_to_goal is not None and baseline.months_to_goal is not None:
        earlier = baseline.months_to_goal - result.months_to_goal
    return ScenarioDelta(
        goal_months_earlier=earlier,
        value_at_target_difference=(
            result.projected_value_at_target_date - baseline.projected_value_at_target_date
        ),
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
