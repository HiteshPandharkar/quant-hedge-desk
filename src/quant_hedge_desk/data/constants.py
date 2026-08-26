"""Canonical external-data contracts."""

from typing import Final


PORTFOLIO_CSV_FIELDS: Final[tuple[str, ...]] = (
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
)

EOD_PRICE_CSV_REQUIRED_FIELDS: Final[frozenset[str]] = frozenset(
    {"date", "symbol", "adjusted_close"}
)
ADJUSTED_CLOSE_FIELD: Final[str] = "adjusted_close"
"""The Week 1 portfolio CSV contract, in its canonical column order."""


__all__ = [
    "ADJUSTED_CLOSE_FIELD",
    "EOD_PRICE_CSV_REQUIRED_FIELDS",
    "PORTFOLIO_CSV_FIELDS",
]
