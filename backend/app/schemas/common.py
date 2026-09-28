from typing import Annotated

from pydantic import Field

from app.services.mapping import to_money

MAX_MONEY = 1_000_000_000.0
"""Upper bound for any EUR input: catches typos and fits the database's Numeric(14, 2)."""

Money = Annotated[float, Field(ge=0, le=MAX_MONEY, allow_inf_nan=False)]
Rate = Annotated[
    float,
    Field(gt=-1, le=1, allow_inf_nan=False, description="Annual rate as a decimal: 0.05 = 5%."),
]


def cents(value: float) -> float:
    """Round a EUR amount to the cent, half up (the same rule as storage)."""
    return float(to_money(value))
