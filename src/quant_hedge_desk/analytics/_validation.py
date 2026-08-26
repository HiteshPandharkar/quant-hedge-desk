"""Shared validation for low-level analytics inputs."""

from __future__ import annotations

from math import isfinite
from typing import Any, Iterable

from quant_hedge_desk.analytics.models import AlignedReturnDataset


def aligned_return_dataset(value: Any) -> AlignedReturnDataset:
    """Require the shared aligned dataset type used by metric adapters."""

    if not isinstance(value, AlignedReturnDataset):
        raise TypeError("dataset must be an AlignedReturnDataset")
    return value


def positive_integer(
    value: Any, name: str, *, error_type: type[ValueError]
) -> int:
    """Validate a positive integer without treating booleans as integers."""

    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise error_type(f"{name} must be a positive integer")
    return value


def return_series(
    values: Iterable[Any],
    name: str,
    *,
    error_type: type[ValueError],
    require_non_empty: bool = False,
    validate_simple_returns: bool = False,
) -> tuple[float, ...]:
    """Parse numeric returns while preserving each metric's input policy."""

    if isinstance(values, (str, bytes)):
        raise error_type(f"{name} must be an iterable of numeric returns")
    try:
        raw_values = tuple(values)
    except TypeError as exc:
        raise error_type(f"{name} must be an iterable of numeric returns") from exc
    if require_non_empty and not raw_values:
        raise error_type(f"{name} must contain at least one observation")

    parsed: list[float] = []
    for index, value in enumerate(raw_values):
        if isinstance(value, bool):
            raise error_type(f"{name}[{index}] must be numeric")
        try:
            result = float(value)
        except (TypeError, ValueError) as exc:
            raise error_type(f"{name}[{index}] must be numeric") from exc
        if not isfinite(result):
            raise error_type(f"{name}[{index}] must be finite")
        if validate_simple_returns and result < -1.0:
            raise error_type(
                f"{name}[{index}] cannot be less than -1 for a simple return"
            )
        parsed.append(result)
    return tuple(parsed)
