"""Shared conversion of immutable result models to JSON-ready values."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Any, Mapping


def json_ready(value: Any) -> Any:
    """Recursively convert supported result values without losing precision."""

    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return {
            item.name: json_ready(getattr(value, item.name)) for item in fields(value)
        }
    if isinstance(value, Mapping):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_ready(item) for item in value]
    return value


__all__ = ["json_ready"]
