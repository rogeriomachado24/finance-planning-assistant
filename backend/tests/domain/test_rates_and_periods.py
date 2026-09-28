from datetime import date

import pytest

from app.domain.errors import InvalidInputError
from app.domain.periods import add_months, first_of_month, months_between
from app.domain.rates import annual_step_factor, annual_to_monthly_rate


class TestAnnualToMonthlyRate:
    @pytest.mark.parametrize("annual", [0.0, 0.03, 0.07, 0.25, -0.2])
    def test_twelve_months_compound_to_the_annual_rate(self, annual):
        monthly = annual_to_monthly_rate(annual)
        assert (1 + monthly) ** 12 - 1 == pytest.approx(annual, abs=1e-12)

    def test_is_lower_than_simple_division_for_positive_rates(self):
        assert annual_to_monthly_rate(0.07) < 0.07 / 12

    @pytest.mark.parametrize("bad", [-1.0, -1.5, 1.01, 7])
    def test_rejects_out_of_range_rates(self, bad):
        with pytest.raises(InvalidInputError):
            annual_to_monthly_rate(bad)


def test_annual_step_factor():
    assert annual_step_factor(0.05, 0) == 1
    assert annual_step_factor(0.05, 2) == pytest.approx(1.1025)
    with pytest.raises(InvalidInputError):
        annual_step_factor(0.05, -1)


class TestPeriods:
    def test_add_months_across_year_boundary(self):
        assert add_months(date(2026, 11, 1), 3) == date(2027, 2, 1)

    def test_add_months_clamps_day_to_month_length(self):
        assert add_months(date(2027, 1, 31), 1) == date(2027, 2, 28)
        assert add_months(date(2028, 1, 31), 1) == date(2028, 2, 29)

    def test_months_between(self):
        assert months_between(date(2026, 10, 1), date(2032, 6, 1)) == 68
        assert months_between(date(2026, 10, 1), date(2026, 10, 1)) == 0
        assert months_between(date(2026, 10, 1), date(2026, 9, 1)) == -1

    def test_months_between_counts_only_completed_months(self):
        assert months_between(date(2026, 10, 15), date(2026, 12, 14)) == 1
        assert months_between(date(2026, 10, 15), date(2026, 12, 15)) == 2

    def test_months_between_inverts_add_months(self):
        start = date(2026, 10, 1)
        for months in (0, 1, 11, 12, 68, 600):
            assert months_between(start, add_months(start, months)) == months

    def test_first_of_month(self):
        assert first_of_month(date(2026, 9, 28)) == date(2026, 9, 1)
