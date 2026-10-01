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


def number_tokens(text: str) -> list[set[Decimal]]:
    """Each number written in the text, with its possible readings: "2.200" -> {2.2, 2200}
    (a European writer's thousands), "20 thousand" -> {20000}."""
    tokens = []
    for match in _NUMBER.finditer(text):
        raw, unit = match.group(1), match.group(2)
        readings = [raw.replace(",", "")]
        if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", raw):
            readings.append(raw.replace(".", ""))
        scale = _SCALE[unit.strip().lower()] if unit else 1
        values = set()
        for reading in readings:
            try:
                values.add((Decimal(reading) * scale).normalize())
            except InvalidOperation:  # pragma: no cover - the pattern only matches digits
                continue
        tokens.append(values)
    return tokens


def numbers_in(text: str) -> set[Decimal]:
    """Every number written in the text: "€80,000" -> 80000, "1.5k" -> 1500, "3.5%" -> 3.5,
    "20 thousand" -> 20000, "2.200" -> 2.2 and 2200. Dates count too ("1 Jun 2031" -> 1 and
    2031), so a changed date is caught."""
    return set().union(*number_tokens(text))


def as_number(value: float) -> Decimal:
    return Decimal(str(abs(value))).normalize()


def only_known_numbers(text: str, source: str) -> bool:
    """True when every number in `text` also appears in `source`."""
    return numbers_in(text) <= numbers_in(source)
