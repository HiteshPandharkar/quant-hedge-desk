"""Immutable records produced while ingesting external data.

Keeping row and field locations separate from the human-readable message makes
validation failures useful both at the command line and in a future report/API.
"""

from __future__ import annotations

from dataclasses import dataclass
from quant_hedge_desk.data.enums import ValidationSeverity
from quant_hedge_desk.domain.models.portfolio import Portfolio


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """One problem found in a source file.

    ``row_number`` uses the one-based physical CSV line number (the header is
    line 1).  It is omitted for file- or portfolio-level issues.
    """

    code: str
    message: str
    severity: ValidationSeverity = ValidationSeverity.ERROR
    row_number: int | None = None
    field: str | None = None

    def __str__(self) -> str:
        location: list[str] = []
        if self.row_number is not None:
            location.append(f"row {self.row_number}")
        if self.field is not None:
            location.append(f"field {self.field}")
        prefix = f"{'/'.join(location)}: " if location else ""
        return f"{prefix}{self.message}"


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """Immutable collection of all issues found in one validation pass."""

    issues: tuple[ValidationIssue, ...] = ()

    @property
    def errors(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity is ValidationSeverity.ERROR)

    @property
    def warnings(self) -> tuple[ValidationIssue, ...]:
        return tuple(
            issue for issue in self.issues if issue.severity is ValidationSeverity.WARNING
        )

    @property
    def is_valid(self) -> bool:
        """Whether validation found no blocking errors."""

        return not self.errors


@dataclass(frozen=True, slots=True)
class PortfolioCSVLoadResult:
    """A reconciled portfolio together with non-blocking ingestion flags."""

    portfolio: Portfolio
    report: ValidationReport


__all__ = ["PortfolioCSVLoadResult", "ValidationIssue", "ValidationReport"]
