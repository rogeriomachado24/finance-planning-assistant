"""Month arithmetic for the projection calendar.

The engine counts whole months from a start date. Month k ends at `add_months(start, k)`.
"""

import calendar
from datetime import date
from functools import lru_cache


def add_months(start: date, months: int) -> date:
    """Shift a date by whole months, clamping the day to the target month's length
    (31 Jan + 1 month -> 28/29 Feb)."""
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


@lru_cache(maxsize=32)
def month_dates(start: date, months: int) -> tuple[date, ...]:
    """End dates of months 0..months. Cached: a Monte Carlo run asks for the same calendar
    once per simulated future."""
    return tuple(add_months(start, m) for m in range(months + 1))


def months_between(start: date, end: date) -> int:
    """Number of whole months from `start` until `end` (negative if `end` is earlier).

    A month only counts once its end date has been reached, so from 1 Sep to 15 Jun
    the result counts complete months up to 1 Jun.
    """
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if months > 0 and end.day < start.day:
        months -= 1
    elif months < 0 and end.day > start.day:
        months += 1
    return months


def first_of_month(day: date) -> date:
    return day.replace(day=1)
