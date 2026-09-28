"""The database enforces the same rules as the domain, and values round-trip exactly."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import AssumptionSetRecord, FinancialProfileRecord, GoalRecord, ScenarioRecord
from app.domain.models import GoalType


def profile_record(**changes) -> FinancialProfileRecord:
    values = {
        "id": 1,
        "age": 32,
        "monthly_net_income": Decimal("2500.00"),
        "other_monthly_income": Decimal("0"),
        "monthly_expenses": Decimal("1700.00"),
        "cash": Decimal("10000.00"),
        "investments": Decimal("15000.00"),
        "monthly_investment_contribution": Decimal("400.00"),
        "debt_balance": Decimal("0"),
        "monthly_debt_payment": Decimal("0"),
    }
    return FinancialProfileRecord(**(values | changes))


def goal_record(**changes) -> GoalRecord:
    values = {
        "name": "Buy a house",
        "goal_type": GoalType.HOUSE,
        "target_amount": Decimal("80000.00"),
        "target_date": date(2032, 6, 1),
    }
    return GoalRecord(**(values | changes))


def assumption_set_record(**changes) -> AssumptionSetRecord:
    values = {
        "name": "base",
        "annual_return": Decimal("0.05"),
        "annual_salary_growth": Decimal("0.02"),
        "annual_expense_growth": Decimal("0.02"),
        "annual_inflation": Decimal("0.02"),
    }
    return AssumptionSetRecord(**(values | changes))


def reload[T](session: Session, record: T) -> T:
    """Save the record, then read the row back from the database (not the session's cache)."""
    session.add(record)
    session.commit()
    session.expunge_all()
    return session.get(type(record), record.id)


def assert_rejected(session: Session, *records: object) -> None:
    session.add_all(records)
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


class TestFinancialProfile:
    def test_round_trips_money_to_the_cent(self, session: Session):
        stored = reload(session, profile_record(cash=Decimal("1234567.89")))
        assert stored.cash == Decimal("1234567.89")
        assert stored.monthly_net_income == Decimal("2500.00")
        assert stored.created_at is not None

    def test_only_one_profile_can_exist(self, session: Session):
        assert_rejected(session, profile_record(id=2))

    @pytest.mark.parametrize(
        "field",
        ["monthly_net_income", "monthly_expenses", "cash", "investments", "debt_balance"],
    )
    def test_rejects_negative_money(self, session: Session, field: str):
        assert_rejected(session, profile_record(**{field: Decimal("-0.01")}))

    def test_age_is_optional_but_bounded(self, session: Session):
        assert reload(session, profile_record(age=None)).age is None
        assert_rejected(session, profile_record(id=1, age=121))


class TestGoal:
    def test_round_trips_goal_type_as_enum(self, session: Session):
        stored = reload(session, goal_record())
        assert stored.goal_type is GoalType.HOUSE
        assert stored.target_date == date(2032, 6, 1)
        assert stored.is_active is True

    def test_at_most_one_active_goal(self, session: Session):
        assert_rejected(session, goal_record(), goal_record(name="Car"))

    def test_inactive_goals_do_not_count(self, session: Session):
        session.add_all(
            [
                goal_record(),
                goal_record(name="Old goal", is_active=False),
                goal_record(name="Older goal", is_active=False),
            ]
        )
        session.commit()
        assert len(session.scalars(select(GoalRecord)).all()) == 3

    def test_rejects_non_positive_target(self, session: Session):
        assert_rejected(session, goal_record(target_amount=Decimal("0")))


class TestAssumptionSet:
    def test_round_trips_rates(self, session: Session):
        stored = reload(session, assumption_set_record(annual_return=Decimal("0.0525")))
        assert stored.annual_return == Decimal("0.0525")

    @pytest.mark.parametrize("rate", ["7", "1.01", "-1"])
    def test_rejects_out_of_range_rates(self, session: Session, rate: str):
        assert_rejected(session, assumption_set_record(annual_return=Decimal(rate)))

    def test_accepts_boundary_and_negative_rates(self, session: Session):
        session.add(
            assumption_set_record(annual_return=Decimal("1"), annual_inflation=Decimal("-0.5"))
        )
        session.commit()

    def test_names_are_unique(self, session: Session):
        assert_rejected(session, assumption_set_record(), assumption_set_record())


class TestScenario:
    def test_round_trips_overrides_as_json(self, session: Session):
        overrides = {"monthly_investment_contribution_delta": 100, "annual_return": 0.03}
        stored = reload(session, ScenarioRecord(name="Higher contribution", overrides=overrides))
        assert stored.overrides == overrides

    def test_overrides_default_to_empty(self, session: Session):
        assert reload(session, ScenarioRecord(name="Current plan")).overrides == {}
