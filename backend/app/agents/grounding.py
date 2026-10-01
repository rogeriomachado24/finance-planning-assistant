"""Checks that a language model only repeats numbers it was given.

Used twice: a parsed request may only contain amounts that appear in the user's message,
and an explanation may only contain numbers that appear in the engine's facts.
"""

import re
from decimal import Decimal, InvalidOperation

_NUMBER = re.compile(
    r"(?<![\w.])(\d+(?:,\d{3})*(?:\.\d+)?)(\s?(?:k|thousand|m|million)\b)?", re.IGNORECASE
)
_SCALE = {"k": 1000, "thousand": 1000, "m": 1_000_000, "million": 1_000_000}


def numbers_in(text: str) -> set[Decimal]:
    """Every number written in the text: "€80,000" -> 80000, "1.5k" -> 1500, "3.5%" -> 3.5,
    "20 thousand" -> 20000. "2.200" counts as both 2.2 and 2200 (a European writer's
    thousands). Dates count too ("1 Jun 2031" -> 1 and 2031), so a changed date is caught."""
    found = set()
    for match in _NUMBER.finditer(text):
        raw, unit = match.group(1), match.group(2)
        readings = [raw.replace(",", "")]
        if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", raw):
            readings.append(raw.replace(".", ""))
        scale = _SCALE[unit.strip().lower()] if unit else 1
        for reading in readings:
            try:
                found.add((Decimal(reading) * scale).normalize())
            except InvalidOperation:  # pragma: no cover - the pattern only matches digits
                continue
    return found


def as_number(value: float) -> Decimal:
    return Decimal(str(abs(value))).normalize()


def only_known_numbers(text: str, source: str) -> bool:
    """True when every number in `text` also appears in `source`."""
    return numbers_in(text) <= numbers_in(source)
