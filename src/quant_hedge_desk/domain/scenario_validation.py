"""Validation and normalization helpers for scenario domain models."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping

from quant_hedge_desk.domain.enums import ScenarioMethodology
from quant_hedge_desk.domain.errors import ScenarioValidationError


def required_text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ScenarioValidationError(f"{path} must be non-empty text")
    return value.strip()


def scenario_date(value: Any, path: str) -> date:
    if isinstance(value, datetime):
        raise ScenarioValidationError(f"{path} must be a date, not a datetime")
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError as exc:
            raise ScenarioValidationError(
                f"{path} must be an ISO date (YYYY-MM-DD)"
            ) from exc
    raise ScenarioValidationError(f"{path} must be a date or ISO date string")


def decimal_number(value: Any, path: str) -> Decimal:
    if isinstance(value, bool):
        raise ScenarioValidationError(f"{path} must be numeric")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ScenarioValidationError(f"{path} must be numeric") from exc
    if not result.is_finite():
        raise ScenarioValidationError(f"{path} must be finite")
    return result


def scenario_methodology(value: Any, path: str) -> ScenarioMethodology:
    if isinstance(value, ScenarioMethodology):
        return value
    try:
        return ScenarioMethodology(required_text(value, path).upper())
    except ValueError as exc:
        allowed = ", ".join(item.value for item in ScenarioMethodology)
        raise ScenarioValidationError(f"{path} must be one of: {allowed}") from exc


def numeric_mapping(
    value: Mapping[str, Any],
    path: str,
    *,
    minimum: Decimal | None = None,
    maximum: Decimal | None = None,
    strictly_positive: bool = False,
) -> Mapping[str, Decimal]:
    if not isinstance(value, Mapping):
        raise ScenarioValidationError(f"{path} must be a mapping")
    normalized: dict[str, Decimal] = {}
    for raw_name, raw_value in value.items():
        name = required_text(raw_name, f"{path} key").upper()
        if name in normalized:
            raise ScenarioValidationError(
                f"{path} contains duplicate key after normalization: {name}"
            )
        number = decimal_number(raw_value, f"{path}.{name}")
        if minimum is not None and number < minimum:
            raise ScenarioValidationError(f"{path}.{name} must be at least {minimum}")
        if maximum is not None and number > maximum:
            raise ScenarioValidationError(f"{path}.{name} must be at most {maximum}")
        if strictly_positive and number <= 0:
            raise ScenarioValidationError(f"{path}.{name} must be positive")
        normalized[name] = number
    return MappingProxyType(dict(sorted(normalized.items())))


def scalar_parameters(
    value: Mapping[str, Any], path: str
) -> Mapping[str, str | int | float | Decimal | bool]:
    if not isinstance(value, Mapping):
        raise ScenarioValidationError(f"{path} must be a mapping")
    result: dict[str, str | int | float | Decimal | bool] = {}
    for raw_name, item in value.items():
        name = required_text(raw_name, f"{path} key")
        if isinstance(item, float) and not isfinite(item):
            raise ScenarioValidationError(f"{path}.{name} must be finite")
        if isinstance(item, Decimal) and not item.is_finite():
            raise ScenarioValidationError(f"{path}.{name} must be finite")
        if not isinstance(item, (str, int, float, Decimal, bool)):
            raise ScenarioValidationError(
                f"{path}.{name} must be a scalar string, number, or boolean"
            )
        result[name] = item
    return MappingProxyType(result)


def check_keys(
    value: Mapping[str, Any],
    required: set[str],
    optional: set[str],
    path: str,
) -> None:
    missing = required - value.keys()
    extra = value.keys() - required - optional
    if missing:
        raise ScenarioValidationError(
            f"{path} is missing: {', '.join(sorted(missing))}"
        )
    if extra:
        raise ScenarioValidationError(
            f"{path} has unknown fields: {', '.join(sorted(extra))}"
        )


__all__ = [
    "check_keys",
    "decimal_number",
    "numeric_mapping",
    "required_text",
    "scalar_parameters",
    "scenario_date",
    "scenario_methodology",
]
