"""Downside-sensitive benchmark exposure metrics."""

from __future__ import annotations

from math import isfinite
from typing import Any, Iterable

import numpy as np

from quant_hedge_desk.analytics.errors import DownsideMetricError, ExposureMetricError
from quant_hedge_desk.analytics.exposure import _aligned_return_pair
from quant_hedge_desk.analytics.models import AlignedReturnDataset
from quant_hedge_desk.analytics._statistics import ols_slope
from quant_hedge_desk.analytics._validation import aligned_return_dataset


def downside_beta(
    portfolio_returns: Iterable[Any],
    benchmark_returns: Iterable[Any],
    *,
    threshold: float = 0.0,
) -> float:
    """Return beta conditional on benchmark returns below ``threshold``.

    The default selects strictly negative benchmark periods.  The conditional
    observations are de-meaned before covariance and variance are calculated,
    matching an OLS regression with an intercept on downside periods.
    """

    if isinstance(threshold, bool):
        raise DownsideMetricError("threshold must be numeric")
    try:
        parsed_threshold = float(threshold)
    except (TypeError, ValueError) as exc:
        raise DownsideMetricError("threshold must be numeric") from exc
    if not isfinite(parsed_threshold):
        raise DownsideMetricError("threshold must be finite")

    try:
        portfolio, benchmark = _aligned_return_pair(
            portfolio_returns, benchmark_returns
        )
    except ExposureMetricError as exc:
        raise DownsideMetricError(str(exc)) from exc

    portfolio_values = np.asarray(portfolio, dtype=np.float64)
    benchmark_values = np.asarray(benchmark, dtype=np.float64)
    downside_mask = benchmark_values < parsed_threshold
    if int(np.count_nonzero(downside_mask)) < 2:
        raise DownsideMetricError(
            "at least two benchmark returns below threshold are required"
        )

    return ols_slope(
        portfolio_values[downside_mask],
        benchmark_values[downside_mask],
        error_type=DownsideMetricError,
        zero_variance_message=(
            "downside beta is undefined for zero downside benchmark variance"
        ),
    )


def downside_beta_from_dataset(
    dataset: AlignedReturnDataset,
    portfolio_symbol: str,
    benchmark_symbol: str,
    *,
    threshold: float = 0.0,
) -> float:
    """Calculate downside beta from two series in an aligned dataset."""

    dataset = aligned_return_dataset(dataset)
    return downside_beta(
        dataset.returns_for(portfolio_symbol),
        dataset.returns_for(benchmark_symbol),
        threshold=threshold,
    )


calculate_downside_beta = downside_beta


__all__ = [
    "DownsideMetricError",
    "calculate_downside_beta",
    "downside_beta",
    "downside_beta_from_dataset",
]
