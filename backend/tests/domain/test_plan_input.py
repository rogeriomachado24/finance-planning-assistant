from datetime import date

import pytest

from app.domain.errors import InvalidInputError
from app.domain.plan_input import Period, months_from_now, per_month, share_of, total


def test_parts_are_added():
    assert total([900, 700]) == 1600
    assert total([2400]) == 2400


@pytest.mark.parametrize("parts", [[], [900, -700]])
def test_total_rejects_no_or_negative_parts(parts):
    with pytest.raises(InvalidInputError):
        total(parts)


def test_a_yearly_amount_is_spread_over_12_months():
    assert per_month(36_000, Period.YEAR) == 3000
    assert per_month(2400, Period.MONTH) == 2400


def test_share_of_a_price():
    assert share_of(20, 300_000) == 60_000
    assert share_of(100, 50_000) == 50_000


@pytest.mark.parametrize(("percent", "amount"), [(0, 300_000), (120, 300_000), (20, 0)])
def test_share_of_rejects_impossible_inputs(percent, amount):
    with pytest.raises(InvalidInputError):
        share_of(percent, amount)


def test_months_from_now_starts_on_the_first_of_this_month():
    assert months_from_now(date(2026, 10, 15), 72) == date(2032, 10, 1)
    with pytest.raises(InvalidInputError):
        months_from_now(date(2026, 10, 15), 0)
