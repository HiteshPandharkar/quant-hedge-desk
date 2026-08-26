"""Benchmark-relative exposure metrics.

The functions in this module operate on already aligned simple returns.  Use
``AlignedReturnDataset`` (and the dataset convenience functions below) when
starting from price histories so that portfolio and benchmark observations
always describe identical intervals.
"""

from __future__ import annotations

from typing import Any, Iterable

import numpy as np

from quant_hedge_desk.analytics.constants import DEFAULT_PERIODS_PER_YEAR
from quant_hedge_desk.analytics.errors import ExposureMetricError
from quant_hedge_desk.analytics.models import AlignedReturnDataset
from quant_hedge_desk.analytics._statistics import ols_slope
from quant_hedge_desk.analytics._validation import (
    aligned_return_dataset,
    positive_integer,
    return_series,
)


def _return_series(values: Iterable[Any], name: str) -> tuple[float, ...]:
    return return_series(values, name, error_type=ExposureMetricError)


def _aligned_return_pair(
    portfolio_returns: Iterable[Any], benchmark_returns: Iterable[Any]
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    portfolio = _return_series(portfolio_returns, "portfolio_returns")
    benchmark = _return_series(benchmark_returns, "benchmark_returns")
    if len(portfolio) != len(benchmark):
        raise ExposureMetricError(
            "portfolio_returns and benchmark_returns must have equal length"
        )
    if len(portfolio) < 2:
        raise ExposureMetricError("at least two aligned return observations are required")
    return portfolio, benchmark


def market_beta(
    portfolio_returns: Iterable[Any], benchmark_returns: Iterable[Any]
) -> float:
    """Return OLS market beta with an intercept.

    Beta is ``sum((p - mean(p)) * (b - mean(b))) / sum((b - mean(b))**2)``.
    This is equivalent to sample covariance divided by sample variance; the
    common ``n - 1`` denominator cancels.
    """

    portfolio, benchmark = _aligned_return_pair(portfolio_returns, benchmark_returns)
    return ols_slope(
        portfolio,
        benchmark,
        error_type=ExposureMetricError,
        zero_variance_message="market beta is undefined for zero benchmark variance",
    )


def tracking_error(
    portfolio_returns: Iterable[Any],
    benchmark_returns: Iterable[Any],
    *,
    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR,
) -> float:
    """Return annualized sample volatility of active simple returns.

    ``periods_per_year`` is configurable for weekly or monthly observations;
    its default of 252 represents daily trading data.
    """

    periods_per_year = positive_integer(
        periods_per_year, "periods_per_year", error_type=ExposureMetricError
    )
    portfolio, benchmark = _aligned_return_pair(portfolio_returns, benchmark_returns)
    active_returns = np.subtract(
        np.asarray(portfolio, dtype=np.float64),
        np.asarray(benchmark, dtype=np.float64),
    )
    return float(active_returns.std(ddof=1) * np.sqrt(periods_per_year))


def market_beta_from_dataset(
    dataset: AlignedReturnDataset, portfolio_symbol: str, benchmark_symbol: str
) -> float:
    """Calculate market beta from two series in an aligned dataset."""

    dataset = aligned_return_dataset(dataset)
    return market_beta(
        dataset.returns_for(portfolio_symbol), dataset.returns_for(benchmark_symbol)
    )


def tracking_error_from_dataset(
    dataset: AlignedReturnDataset,
    portfolio_symbol: str,
    benchmark_symbol: str,
    *,
    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR,
) -> float:
    """Calculate annualized tracking error from an aligned dataset."""

    dataset = aligned_return_dataset(dataset)
    return tracking_error(
        dataset.returns_for(portfolio_symbol),
        dataset.returns_for(benchmark_symbol),
        periods_per_year=periods_per_year,
    )


# Verb-based aliases make the public API natural in application/report code.
calculate_beta = market_beta
calculate_market_beta = market_beta
calculate_tracking_error = tracking_error


__all__ = [
    "DEFAULT_PERIODS_PER_YEAR",
    "ExposureMetricError",
    "calculate_beta",
    "calculate_market_beta",
    "calculate_tracking_error",
    "market_beta",
    "market_beta_from_dataset",
    "tracking_error",
    "tracking_error_from_dataset",
]
