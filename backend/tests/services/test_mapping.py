from decimal import Decimal

import pytest

from app.domain.errors import InvalidInputError
from app.domain.scenarios import ScenarioOverrides
from app.services.mapping import overrides_from_dict, overrides_to_dict, to_money, to_rate


@pytest.mark.parametrize(
    ("value", "stored"),
    [
        (2500, "2500.00"),
        (0.005, "0.01"),  # half up
        (2.675, "2.68"),  # the float is 2.67499999...; converting via str() keeps "2.675"
        (1234567.891, "1234567.89"),
    ],
)
def test_money_is_rounded_to_the_cent(value: float, stored: str):
    assert to_money(value) == Decimal(stored)


def test_rates_keep_six_decimal_places():
    assert to_rate(0.0525) == Decimal("0.052500")
    assert to_rate(0.07) == Decimal("0.070000")


def test_overrides_store_only_the_fields_that_are_set():
    overrides = ScenarioOverrides(monthly_investment_contribution_delta=100, annual_return=0.03)
    data = overrides_to_dict(overrides)
    assert data == {"monthly_investment_contribution_delta": 100, "annual_return": 0.03}
    assert overrides_from_dict(data) == overrides


def test_unknown_override_is_rejected():
    with pytest.raises(InvalidInputError, match="unknown scenario overrides: bonus"):
        overrides_from_dict({"bonus": 5000})
