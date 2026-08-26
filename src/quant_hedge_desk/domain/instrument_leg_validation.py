"""Parsing and validation helpers for derivative-leg domain contracts."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Any, Mapping, TypeVar

from quant_hedge_desk.domain.enums import InstrumentType
from quant_hedge_desk.domain.errors import InstrumentValidationError
from quant_hedge_desk.domain.models._validation import ModelValidator


EnumValue = TypeVar("EnumValue")
validator = ModelValidator(InstrumentValidationError)


def enum_value(value: Any, enum_type: type[EnumValue], path: str) -> EnumValue:
    """Normalize a controlled vocabulary value or raise a domain error."""

    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        allowed = ", ".join(member.value for member in enum_type)  # type: ignore[attr-defined]
        raise InstrumentValidationError(f"{path} must be one of: {allowed}") from exc


def expiry_date(value: Any, path: str = "expiry") -> date:
    """Normalize a date object or ISO date string."""

    if isinstance(value, datetime):
        raise InstrumentValidationError(f"{path} must be a date, not a datetime")
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError as exc:
            raise InstrumentValidationError(
                f"{path} must be an ISO date (YYYY-MM-DD)"
            ) from exc
    raise InstrumentValidationError(f"{path} must be a date or ISO date string")


def quote_datetime(value: Any, path: str = "quote_timestamp") -> datetime:
    """Normalize a datetime object or ISO datetime string."""

    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise InstrumentValidationError(f"{path} must be an ISO datetime") from exc
    raise InstrumentValidationError(f"{path} must be a datetime or ISO datetime string")


def non_negative_decimal(value: Any, path: str) -> Decimal:
    """Normalize a finite decimal constrained to zero or greater."""

    result = validator.decimal(value, path)
    if result < 0:
        raise InstrumentValidationError(f"{path} must be non-negative")
    return result


def immutable_liquidity_attributes(value: Any) -> Mapping[str, Any]:
    """Copy liquidity metadata into a read-only mapping."""

    attributes = validator.mapping(value, "liquidity_attributes")
    return MappingProxyType(dict(attributes))


def leg_mapping(
    value: Any,
    *,
    path: str,
    required: set[str],
    expected_instrument_type: InstrumentType,
) -> Mapping[str, Any]:
    """Validate a serialized leg's shape and instrument discriminator."""

    mapping = validator.mapping(value, path)
    validator.keys(mapping, required, path)
    actual = enum_value(mapping["instrument_type"], InstrumentType, "instrument_type")
    if actual is not expected_instrument_type:
        raise InstrumentValidationError(
            f"instrument_type must be {expected_instrument_type.value} for a {path}"
        )
    return mapping


__all__ = [
    "enum_value",
    "expiry_date",
    "immutable_liquidity_attributes",
    "leg_mapping",
    "non_negative_decimal",
    "quote_datetime",
    "validator",
]
