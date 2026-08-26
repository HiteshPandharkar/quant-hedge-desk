"""Compatibility imports for structured data-validation results."""

from quant_hedge_desk.data.enums import ValidationSeverity
from quant_hedge_desk.data.models import ValidationIssue, ValidationReport

__all__ = ["ValidationIssue", "ValidationReport", "ValidationSeverity"]
