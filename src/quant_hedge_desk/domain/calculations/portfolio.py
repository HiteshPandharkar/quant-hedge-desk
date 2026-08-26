"""Pure arithmetic for portfolio reconciliation."""

from decimal import Decimal
from typing import Iterable


def calculate_holding_market_value(quantity: Decimal, price: Decimal) -> Decimal:
    """Calculate a holding's market value from quantity and unit price."""

    return quantity * price


def calculate_total_market_value(market_values: Iterable[Decimal]) -> Decimal:
    """Sum market values using an exact decimal zero."""

    return sum(market_values, Decimal("0"))


def relative_difference(actual: Decimal, expected: Decimal) -> Decimal:
    """Return the absolute difference relative to the expected value."""

    return abs(actual - expected) / abs(expected)


__all__ = [
    "calculate_holding_market_value",
    "calculate_total_market_value",
    "relative_difference",
]
