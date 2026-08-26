"""Domain-wide reconciliation tolerances."""

from decimal import Decimal
from typing import Final


MARKET_VALUE_RECONCILIATION_TOLERANCE: Final[Decimal] = Decimal("0.001")
"""Maximum relative market-value difference (0.10%)."""

WEIGHT_RECONCILIATION_TOLERANCE: Final[Decimal] = Decimal("0.0001")
"""Maximum absolute weight difference (0.01 percentage points)."""

MINIMUM_SIMPLE_RETURN: Final[Decimal] = Decimal("-1")
"""Lowest valid simple return: complete loss of the asset value."""

TOTAL_SCENARIO_PROBABILITY: Final[Decimal] = Decimal("1")
"""Required total when scenario paths carry explicit probabilities."""


__all__ = [
    "MARKET_VALUE_RECONCILIATION_TOLERANCE",
    "MINIMUM_SIMPLE_RETURN",
    "TOTAL_SCENARIO_PROBABILITY",
    "WEIGHT_RECONCILIATION_TOLERANCE",
]
