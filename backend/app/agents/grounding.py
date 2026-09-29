"""Checks that a language model only repeats numbers it was given.

Used twice: a parsed request may only contain amounts that appear in the user's message,
and an explanation may only contain numbers that appear in the engine's facts.
"""

import re
from decimal import Decimal, InvalidOperation

_NUMBER = re.compile(r"(?<![\w.])(\d+(?:,\d{3})*(?:\.\d+)?)(\s?k\b)?", re.IGNORECASE)


def numbers_in(text: str) -> set[Decimal]:
    """Every number written in the text: "€80,000" -> 80000, "1.5k" -> 1500, "3.5%" -> 3.5.
    Dates count too ("1 Jun 2031" -> 1 and 2031), so a changed date is caught."""
    found = set()
    for match in _NUMBER.finditer(text):
        try:
            value = Decimal(match.group(1).replace(",", ""))
        except InvalidOperation:  # pragma: no cover - the pattern only matches digits
            continue
        found.add((value * 1000 if match.group(2) else value).normalize())
    return found


def as_number(value: float) -> Decimal:
    return Decimal(str(abs(value))).normalize()


def only_known_numbers(text: str, source: str) -> bool:
    """True when every number in `text` also appears in `source`."""
    return numbers_in(text) <= numbers_in(source)
