"""Portfolio dataclasses and their invariant checks.

The portfolio is a dated, immutable snapshot.  Monetary values and weights use
``Decimal`` so that ingestion and audit checks do not depend on binary floating
point rounding.  Classification fields remain strings because their controlled
vocabularies are intentionally deferred by the Week 1 requirements.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterable, Mapping

from quant_hedge_desk.domain.calculations.portfolio import (
    calculate_holding_market_value,
    calculate_total_market_value,
    relative_difference,
)
from quant_hedge_desk.domain.constants import (
    MARKET_VALUE_RECONCILIATION_TOLERANCE,
    WEIGHT_RECONCILIATION_TOLERANCE,
)
from quant_hedge_desk.domain.models._validation import ModelValidator


class PortfolioValidationError(ValueError):
    """Raised when a holding or portfolio snapshot is invalid."""


_validate = ModelValidator(PortfolioValidationError)


def _date(value: Any, path: str) -> date:
    if isinstance(value, datetime):
        raise PortfolioValidationError(f"{path} must be a date, not a datetime")
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError as exc:
            raise PortfolioValidationError(f"{path} must be an ISO date (YYYY-MM-DD)") from exc
    raise PortfolioValidationError(f"{path} must be a date or ISO date string")


@dataclass(frozen=True, slots=True)
class PortfolioHolding:
    """One long equity position in a client portfolio snapshot."""

    portfolio_id: str
    as_of_date: date
    symbol: str
    quantity: Decimal
    price: Decimal
    market_value: Decimal
    portfolio_weight: Decimal
    sector: str
    benchmark_weight: Decimal
    liquidity_bucket: str
    hedging_restriction: str
    data_source: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "portfolio_id", _validate.required_text(self.portfolio_id, "portfolio_id"))
        object.__setattr__(self, "as_of_date", _date(self.as_of_date, "as_of_date"))
        object.__setattr__(self, "symbol", _validate.required_text(self.symbol, "symbol").upper())
        object.__setattr__(self, "quantity", _validate.positive_decimal(self.quantity, "quantity"))
        object.__setattr__(self, "price", _validate.positive_decimal(self.price, "price"))
        object.__setattr__(self, "market_value", _validate.positive_decimal(self.market_value, "market_value"))
        object.__setattr__(
            self,
            "portfolio_weight",
            _validate.fraction(self.portfolio_weight, "portfolio_weight", include_zero=False, percentage_allowed=True),
        )
        object.__setattr__(self, "sector", _validate.required_text(self.sector, "sector"))
        object.__setattr__(
            self, "benchmark_weight", _validate.fraction(self.benchmark_weight, "benchmark_weight", include_zero=True, percentage_allowed=True)
        )
        object.__setattr__(
            self,
            "liquidity_bucket",
            _validate.required_text(self.liquidity_bucket, "liquidity_bucket"),
        )
        object.__setattr__(
            self,
            "hedging_restriction",
            _validate.required_text(self.hedging_restriction, "hedging_restriction"),
        )
        object.__setattr__(self, "data_source", _validate.required_text(self.data_source, "data_source"))

        if relative_difference(self.market_value, self.calculated_market_value) > MARKET_VALUE_RECONCILIATION_TOLERANCE:
            raise PortfolioValidationError(
                f"holding {self.symbol} market_value does not reconcile to quantity * price "
                "within 0.10%"
            )

    @property
    def calculated_market_value(self) -> Decimal:
        """Market value calculated from quantity and price."""

        return calculate_holding_market_value(self.quantity, self.price)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> PortfolioHolding:
        value = _validate.mapping(value, "holding")
        required = {
            "portfolio_id",
            "as_of_date",
            "symbol",
            "quantity",
            "price",
            "market_value",
            "portfolio_weight",
            "sector",
            "benchmark_weight",
            "liquidity_bucket",
            "hedging_restriction",
            "data_source",
        }
        _validate.keys(value, required, "holding")
        return cls(**value)


@dataclass(frozen=True, slots=True)
class Portfolio:
    """A reconciled collection of holdings at one valuation date."""

    portfolio_id: str
    as_of_date: date
    holdings: tuple[PortfolioHolding, ...]
    supplied_total_market_value: Decimal | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "portfolio_id", _validate.required_text(self.portfolio_id, "portfolio_id"))
        object.__setattr__(self, "as_of_date", _date(self.as_of_date, "as_of_date"))
        holdings = tuple(self.holdings)
        if not holdings:
            raise PortfolioValidationError("holdings must be non-empty")
        if any(not isinstance(holding, PortfolioHolding) for holding in holdings):
            raise PortfolioValidationError("holdings must contain only PortfolioHolding objects")
        object.__setattr__(self, "holdings", holdings)

        wrong_ids = sorted({h.portfolio_id for h in holdings if h.portfolio_id != self.portfolio_id})
        if wrong_ids:
            raise PortfolioValidationError("all holdings must have the portfolio's portfolio_id")
        wrong_dates = sorted({h.as_of_date for h in holdings if h.as_of_date != self.as_of_date})
        if wrong_dates:
            raise PortfolioValidationError("all holdings must have the portfolio's as_of_date")

        symbols = [holding.symbol for holding in holdings]
        duplicates = sorted({symbol for symbol in symbols if symbols.count(symbol) > 1})
        if duplicates:
            raise PortfolioValidationError(f"duplicate holdings: {', '.join(duplicates)}")

        weight_sum = sum((holding.portfolio_weight for holding in holdings), Decimal("0"))
        if abs(weight_sum - Decimal("1")) > WEIGHT_RECONCILIATION_TOLERANCE:
            raise PortfolioValidationError(
                "portfolio weights must sum to 100% within 0.01 percentage points"
            )

        total = self.total_market_value
        for holding in holdings:
            calculated_weight = holding.market_value / total
            if abs(holding.portfolio_weight - calculated_weight) > WEIGHT_RECONCILIATION_TOLERANCE:
                raise PortfolioValidationError(
                    f"holding {holding.symbol} portfolio_weight does not reconcile to market_value "
                    "within 0.01 percentage points"
                )

        if self.supplied_total_market_value is not None:
            supplied_total = _validate.positive_decimal(
                self.supplied_total_market_value, "supplied_total_market_value"
            )
            object.__setattr__(self, "supplied_total_market_value", supplied_total)
            if relative_difference(total, supplied_total) > MARKET_VALUE_RECONCILIATION_TOLERANCE:
                raise PortfolioValidationError(
                    "calculated portfolio market value does not reconcile to supplied total "
                    "within 0.10%"
                )

    @property
    def total_market_value(self) -> Decimal:
        """Sum of supplied, reconciled position market values."""

        return calculate_total_market_value(
            holding.market_value for holding in self.holdings
        )

    @property
    def calculated_total_market_value(self) -> Decimal:
        """Sum independently calculated from each holding's quantity and price."""

        return calculate_total_market_value(
            holding.calculated_market_value for holding in self.holdings
        )

    def holding(self, symbol: str) -> PortfolioHolding:
        """Return a holding by symbol, or raise ``KeyError`` when it is absent."""

        normalized = _validate.required_text(symbol, "symbol").upper()
        for holding in self.holdings:
            if holding.symbol == normalized:
                return holding
        raise KeyError(normalized)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> Portfolio:
        value = _validate.mapping(value, "portfolio")
        _validate.keys(
            value,
            {"portfolio_id", "as_of_date", "holdings"},
            "portfolio",
            optional={"supplied_total_market_value"},
        )
        rows = _validate.sequence(value["holdings"], "portfolio.holdings")
        return cls(
            portfolio_id=value["portfolio_id"],
            as_of_date=value["as_of_date"],
            holdings=tuple(
                row if isinstance(row, PortfolioHolding) else PortfolioHolding.from_mapping(row)
                for row in rows
            ),
            supplied_total_market_value=value.get("supplied_total_market_value"),
        )

    @classmethod
    def from_holdings(
        cls,
        holdings: Iterable[PortfolioHolding | Mapping[str, Any]],
        *,
        supplied_total_market_value: Any | None = None,
    ) -> Portfolio:
        """Build a snapshot from rows, inferring their common id and date."""

        parsed = tuple(
            item if isinstance(item, PortfolioHolding) else PortfolioHolding.from_mapping(item)
            for item in holdings
        )
        if not parsed:
            raise PortfolioValidationError("holdings must be non-empty")
        return cls(
            portfolio_id=parsed[0].portfolio_id,
            as_of_date=parsed[0].as_of_date,
            holdings=parsed,
            supplied_total_market_value=supplied_total_market_value,
        )


# Explicit aliases make the ubiquitous domain terms convenient without creating
# competing implementations.
Holding = PortfolioHolding
PortfolioSnapshot = Portfolio


__all__ = [
    "Holding",
    "MARKET_VALUE_RECONCILIATION_TOLERANCE",
    "Portfolio",
    "PortfolioHolding",
    "PortfolioSnapshot",
    "PortfolioValidationError",
    "WEIGHT_RECONCILIATION_TOLERANCE",
]
