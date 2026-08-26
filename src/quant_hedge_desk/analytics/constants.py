"""Defaults and methodology constants for analytics calculations."""

from decimal import Decimal
from typing import Final


DEFAULT_CONFIDENCE_LEVEL: Final[float] = 0.99
DEFAULT_PERIODS_PER_YEAR: Final[int] = 252

DEFAULT_SINGLE_NAME_LIMIT: Final[Decimal] = Decimal("0.10")
DEFAULT_TOP_N: Final[int] = 5
DEFAULT_TOP_N_MINIMUM: Final[Decimal] = Decimal("0.30")
DEFAULT_TOP_N_MAXIMUM: Final[Decimal] = Decimal("0.40")


__all__ = [
    "DEFAULT_CONFIDENCE_LEVEL",
    "DEFAULT_PERIODS_PER_YEAR",
    "DEFAULT_SINGLE_NAME_LIMIT",
    "DEFAULT_TOP_N",
    "DEFAULT_TOP_N_MAXIMUM",
    "DEFAULT_TOP_N_MINIMUM",
]
