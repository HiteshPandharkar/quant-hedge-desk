"""File loaders shared by case-study configuration adapters."""

from __future__ import annotations

import csv
import warnings
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping, TextIO

import yaml

from quant_hedge_desk.data.constants import PORTFOLIO_CSV_FIELDS
from quant_hedge_desk.data.enums import ValidationSeverity
from quant_hedge_desk.data.models import (
    PortfolioCSVLoadResult,
    ValidationIssue,
    ValidationReport,
)
from quant_hedge_desk.domain.models.portfolio import (
    Portfolio,
    PortfolioHolding,
    PortfolioValidationError,
)
from quant_hedge_desk.domain.models.rebalancing import RebalancingStressPolicy


class DataLoadError(ValueError):
    """Raised when an external data file cannot be read or decoded."""


class PortfolioCSVValidationError(DataLoadError):
    """Raised when a portfolio CSV contains one or more blocking issues."""

    def __init__(self, path: str | Path, report: ValidationReport) -> None:
        self.path = Path(path)
        self.report = report
        details = "; ".join(str(issue) for issue in report.errors)
        super().__init__(f"Invalid portfolio CSV {self.path}: {details}")


class PortfolioCSVWarning(UserWarning):
    """Emitted when a portfolio loads with non-blocking validation flags."""


def load_yaml_mapping(path: str | Path) -> Mapping[str, Any]:
    """Load a YAML configuration safely and require an object at its root."""

    source = Path(path)
    try:
        with source.open(encoding="utf-8") as stream:
            value = yaml.safe_load(stream)
    except (OSError, yaml.YAMLError) as exc:
        raise DataLoadError(f"Could not load YAML configuration {source}: {exc}") from exc
    if not isinstance(value, Mapping):
        raise DataLoadError(f"YAML configuration {source} must contain a mapping at its root")
    return value


def load_rebalancing_stress_policy(path: str | Path) -> RebalancingStressPolicy:
    """Load and strictly validate a versioned rebalancing-stress policy."""

    return RebalancingStressPolicy.from_mapping(load_yaml_mapping(path))


def _iso_date(value: date | str, name: str) -> date:
    if isinstance(value, datetime):
        raise ValueError(f"{name} must be a date, not a datetime")
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError as exc:
            raise ValueError(f"{name} must be an ISO date (YYYY-MM-DD)") from exc
    raise TypeError(f"{name} must be a date or ISO date string")


def _read_portfolio_rows(source: TextIO) -> tuple[list[dict[str, str]], list[ValidationIssue]]:
    """Read rows while retaining physical line numbers for diagnostics."""

    reader = csv.reader(source, strict=True)
    try:
        header = next(reader)
    except StopIteration:
        return [], [ValidationIssue("empty_file", "file is empty")]
    except csv.Error as exc:
        return [], [ValidationIssue("malformed_csv", f"could not parse header: {exc}")]

    header = [column.strip() for column in header]
    issues: list[ValidationIssue] = []
    if len(header) != len(set(header)):
        duplicates = sorted({column for column in header if header.count(column) > 1})
        issues.append(
            ValidationIssue(
                "duplicate_columns",
                f"duplicate columns: {', '.join(duplicates)}",
                row_number=1,
            )
        )
    missing = sorted(set(PORTFOLIO_CSV_FIELDS) - set(header))
    extra = sorted(set(header) - set(PORTFOLIO_CSV_FIELDS))
    if missing:
        issues.append(
            ValidationIssue(
                "missing_columns",
                f"missing required columns: {', '.join(missing)}",
                row_number=1,
            )
        )
    if extra:
        issues.append(
            ValidationIssue(
                "unknown_columns",
                f"unknown columns: {', '.join(extra)}",
                row_number=1,
            )
        )
    if issues:
        return [], issues

    rows: list[dict[str, str]] = []
    try:
        for values in reader:
            line_number = reader.line_num
            if not values or all(not value.strip() for value in values):
                continue
            if len(values) != len(header):
                issues.append(
                    ValidationIssue(
                        "column_count",
                        f"expected {len(header)} columns but found {len(values)}",
                        row_number=line_number,
                    )
                )
                continue
            row = dict(zip(header, values, strict=True))
            row["__line_number__"] = str(line_number)
            rows.append(row)
    except csv.Error as exc:
        issues.append(
            ValidationIssue(
                "malformed_csv", f"could not parse CSV: {exc}", row_number=reader.line_num
            )
        )
    if not rows and not issues:
        issues.append(ValidationIssue("no_holdings", "file contains no holding rows"))
    return rows, issues


def _validate_portfolio_rows(
    rows: list[dict[str, str]],
    *,
    supplied_total_market_value: Any | None,
    valuation_date: date | str | None,
    max_price_age_days: int | None,
) -> tuple[Portfolio | None, ValidationReport]:
    issues: list[ValidationIssue] = []
    holdings: list[PortfolioHolding] = []
    parsed_rows: list[tuple[PortfolioHolding, int]] = []
    row_numbers: dict[str, list[int]] = {}

    for raw_row in rows:
        row = raw_row.copy()
        line_number = int(row.pop("__line_number__"))
        symbol = row.get("symbol", "").strip().upper()
        row_numbers.setdefault(symbol, []).append(line_number)
        blank_fields = [name for name in PORTFOLIO_CSV_FIELDS if not row[name].strip()]
        if blank_fields:
            for field in blank_fields:
                issues.append(
                    ValidationIssue(
                        "missing_value",
                        "required value is blank",
                        row_number=line_number,
                        field=field,
                    )
                )
            continue
        try:
            holding = PortfolioHolding.from_mapping(row)
            holdings.append(holding)
            parsed_rows.append((holding, line_number))
        except PortfolioValidationError as exc:
            issues.append(ValidationIssue("invalid_holding", str(exc), row_number=line_number))

    for symbol, locations in row_numbers.items():
        if symbol and len(locations) > 1:
            for line_number in locations:
                issues.append(
                    ValidationIssue(
                        "duplicate_holding",
                        f"duplicate holding symbol {symbol}",
                        row_number=line_number,
                        field="symbol",
                    )
                )

    portfolio_ids = {holding.portfolio_id for holding, _ in parsed_rows}
    if len(portfolio_ids) > 1:
        expected = parsed_rows[0][0].portfolio_id
        for holding, line_number in parsed_rows:
            if holding.portfolio_id != expected:
                issues.append(
                    ValidationIssue(
                        "inconsistent_portfolio_id",
                        f"portfolio_id {holding.portfolio_id!r} does not match {expected!r}",
                        row_number=line_number,
                        field="portfolio_id",
                    )
                )

    snapshot_dates = {holding.as_of_date for holding, _ in parsed_rows}
    if len(snapshot_dates) > 1:
        expected = parsed_rows[0][0].as_of_date
        for holding, line_number in parsed_rows:
            if holding.as_of_date != expected:
                issues.append(
                    ValidationIssue(
                        "inconsistent_as_of_date",
                        f"as_of_date {holding.as_of_date} does not match {expected}",
                        row_number=line_number,
                        field="as_of_date",
                    )
                )

    if valuation_date is not None or max_price_age_days is not None:
        if valuation_date is None or max_price_age_days is None:
            raise ValueError(
                "valuation_date and max_price_age_days must be supplied together "
                "for freshness validation"
            )
        valuation = _iso_date(valuation_date, "valuation_date")
        if (
            isinstance(max_price_age_days, bool)
            or not isinstance(max_price_age_days, int)
            or max_price_age_days < 0
        ):
            raise ValueError("max_price_age_days must be a non-negative integer")
        for holding, line_number in parsed_rows:
            age = (valuation - holding.as_of_date).days
            if age < 0:
                issues.append(
                    ValidationIssue(
                        "future_snapshot",
                        f"as_of_date {holding.as_of_date} is after valuation date {valuation}",
                        row_number=line_number,
                        field="as_of_date",
                    )
                )
            elif age > max_price_age_days:
                issues.append(
                    ValidationIssue(
                        "stale_price",
                        f"price is {age} days old; maximum is {max_price_age_days}",
                        severity=ValidationSeverity.WARNING,
                        row_number=line_number,
                        field="price",
                    )
                )

    if any(issue.severity is ValidationSeverity.ERROR for issue in issues):
        return None, ValidationReport(tuple(issues))
    try:
        portfolio = Portfolio.from_holdings(
            holdings, supplied_total_market_value=supplied_total_market_value
        )
    except PortfolioValidationError as exc:
        issues.append(ValidationIssue("portfolio_reconciliation", str(exc)))
        return None, ValidationReport(tuple(issues))
    return portfolio, ValidationReport(tuple(issues))


def load_portfolio_csv_with_report(
    path: str | Path,
    *,
    supplied_total_market_value: Any | None = None,
    valuation_date: date | str | None = None,
    max_price_age_days: int | None = None,
) -> PortfolioCSVLoadResult:
    """Load and reconcile a Week 1 portfolio CSV.

    Staleness is inherently use-case dependent.  When ``valuation_date`` and
    ``max_price_age_days`` are provided, stale prices are retained but flagged
    as warnings; future-dated observations remain blocking errors.
    """

    source = Path(path)
    try:
        with source.open(encoding="utf-8-sig", newline="") as stream:
            rows, read_issues = _read_portfolio_rows(stream)
    except OSError as exc:
        raise DataLoadError(f"Could not load portfolio CSV {source}: {exc}") from exc

    if read_issues:
        raise PortfolioCSVValidationError(source, ValidationReport(tuple(read_issues)))
    portfolio, report = _validate_portfolio_rows(
        rows,
        supplied_total_market_value=supplied_total_market_value,
        valuation_date=valuation_date,
        max_price_age_days=max_price_age_days,
    )
    if portfolio is None:
        raise PortfolioCSVValidationError(source, report)
    return PortfolioCSVLoadResult(portfolio, report)


def load_portfolio_csv(
    path: str | Path,
    *,
    supplied_total_market_value: Any | None = None,
    valuation_date: date | str | None = None,
    max_price_age_days: int | None = None,
) -> Portfolio:
    """Load a portfolio CSV and return its reconciled immutable snapshot.

    Non-blocking issues are emitted as one :class:`PortfolioCSVWarning`.  Use
    :func:`load_portfolio_csv_with_report` when structured warning details are
    needed by the caller.
    """

    result = load_portfolio_csv_with_report(
        path,
        supplied_total_market_value=supplied_total_market_value,
        valuation_date=valuation_date,
        max_price_age_days=max_price_age_days,
    )
    if result.report.warnings:
        details = "; ".join(str(issue) for issue in result.report.warnings)
        warnings.warn(
            f"Portfolio CSV {Path(path)} loaded with validation flags: {details}",
            PortfolioCSVWarning,
            stacklevel=2,
        )
    return result.portfolio


__all__ = [
    "DataLoadError",
    "PORTFOLIO_CSV_FIELDS",
    "PortfolioCSVLoadResult",
    "PortfolioCSVValidationError",
    "PortfolioCSVWarning",
    "load_portfolio_csv",
    "load_portfolio_csv_with_report",
    "load_rebalancing_stress_policy",
    "load_yaml_mapping",
]
