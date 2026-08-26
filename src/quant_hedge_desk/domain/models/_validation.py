"""Shared, configurable validation primitives for domain models."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence


class ModelValidator:
    """Validate serialization-friendly values with a model-specific error type."""

    def __init__(
        self,
        error_type: type[ValueError],
        *,
        percentages_allowed: bool = False,
    ) -> None:
        self._error_type = error_type
        self._percentages_allowed = percentages_allowed

    def decimal(
        self,
        value: Any,
        path: str,
        *,
        percentage_allowed: bool | None = None,
    ) -> Decimal:
        if isinstance(value, bool):
            raise self._error_type(f"{path} must be numeric")
        allow_percentage = (
            self._percentages_allowed
            if percentage_allowed is None
            else percentage_allowed
        )
        divisor = Decimal("1")
        if allow_percentage and isinstance(value, str) and value.strip().endswith("%"):
            value = value.strip()[:-1].strip()
            divisor = Decimal("100")
        try:
            result = Decimal(str(value)) / divisor
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise self._error_type(f"{path} must be numeric") from exc
        if not result.is_finite():
            raise self._error_type(f"{path} must be finite")
        return result

    def fraction(
        self,
        value: Any,
        path: str,
        *,
        include_zero: bool,
        percentage_allowed: bool | None = None,
    ) -> Decimal:
        result = self.decimal(
            value, path, percentage_allowed=percentage_allowed
        )
        lower_ok = result >= 0 if include_zero else result > 0
        if not lower_ok or result > 1:
            boundary = "[0, 1]" if include_zero else "(0, 1]"
            raise self._error_type(f"{path} must be in {boundary}")
        return result

    def positive_decimal(self, value: Any, path: str) -> Decimal:
        result = self.decimal(value, path)
        if result <= 0:
            raise self._error_type(f"{path} must be positive")
        return result

    def positive_int(self, value: Any, path: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise self._error_type(f"{path} must be a positive integer")
        return value

    def required_text(self, value: Any, path: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise self._error_type(f"{path} must be non-empty text")
        return value.strip()

    def mapping(self, value: Any, path: str) -> Mapping[str, Any]:
        if not isinstance(value, Mapping):
            raise self._error_type(f"{path} must be a mapping")
        return value

    def sequence(self, value: Any, path: str) -> Sequence[Any]:
        if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
            raise self._error_type(f"{path} must be a sequence")
        return value

    def keys(
        self,
        value: Mapping[str, Any],
        required: set[str],
        path: str,
        *,
        optional: set[str] | None = None,
    ) -> None:
        optional = optional or set()
        missing = required - value.keys()
        extra = value.keys() - required - optional
        if missing:
            raise self._error_type(
                f"{path} is missing: {', '.join(sorted(missing))}"
            )
        if extra:
            raise self._error_type(
                f"{path} has unknown fields: {', '.join(sorted(extra))}"
            )
