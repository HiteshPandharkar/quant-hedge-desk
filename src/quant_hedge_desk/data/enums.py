"""Controlled vocabularies used by data-ingestion components."""

from enum import StrEnum


class ValidationSeverity(StrEnum):
    """Severity assigned to an ingestion issue."""

    ERROR = "ERROR"
    WARNING = "WARNING"


__all__ = ["ValidationSeverity"]
