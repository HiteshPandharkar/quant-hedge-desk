"""Historical tail-risk and path-dependent loss metrics.

Returns in this module are simple, signed returns: gains are positive and
losses are negative.  Consequently historical VaR and expected shortfall are
also signed return thresholds.  This matches the mandate's expression of the
99% expected-shortfall limit as ``-12%`` rather than as a positive loss amount.
"""

from __future__ import annotations

from decimal import Decimal
from math import ceil, isfinite
from typing import Any, Iterable

import numpy as np

from quant_hedge_desk.analytics.constants import DEFAULT_CONFIDENCE_LEVEL
from quant_hedge_desk.analytics.errors import RiskMetricError
from quant_hedge_desk.analytics.models import AlignedReturnDataset, HistoricalRiskMetrics
from quant_hedge_desk.analytics._validation import aligned_return_dataset, return_series


def _return_series(values: Iterable[Any], name: str = "returns") -> tuple[float, ...]:
    return return_series(
        values,
        name,
        error_type=RiskMetricError,
        require_non_empty=True,
        validate_simple_returns=True,
    )


def _confidence(value: Any) -> float:
    if isinstance(value, bool):
        raise RiskMetricError("confidence_level must be numeric")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise RiskMetricError("confidence_level must be numeric") from exc
    if not isfinite(result) or not 0.0 < result < 1.0:
        raise RiskMetricError("confidence_level must be a finite number in (0, 1)")
    return result


def _tail_observation_mass(confidence_level: float, observation_count: int) -> float:
    """Return tail mass in observation units without binary cutoff drift."""

    return float(
        (Decimal("1") - Decimal(str(confidence_level))) * observation_count
    )


def value_at_risk(
    returns: Iterable[Any], *, confidence_level: float = DEFAULT_CONFIDENCE_LEVEL
) -> float:
    """Return the empirical lower-tail VaR as a signed return.

    The calculation uses the inverse empirical CDF (the nearest-rank,
    non-interpolated quantile).  At 99% confidence, for example, the result is
    the observed 1st-percentile return.  A result of ``-0.10`` denotes a 10%
    loss threshold.
    """

    observations = np.sort(np.asarray(_return_series(returns), dtype=np.float64))
    confidence = _confidence(confidence_level)
    tail_observation_mass = _tail_observation_mass(confidence, len(observations))
    index = max(0, ceil(tail_observation_mass) - 1)
    return float(observations[index])


def expected_shortfall(
    returns: Iterable[Any], *, confidence_level: float = DEFAULT_CONFIDENCE_LEVEL
) -> float:
    """Return empirical expected shortfall as a signed lower-tail mean.

    Every observation has equal empirical probability.  If the requested tail
    probability ends part-way through an observation's probability mass, the
    boundary observation is included fractionally.  This avoids an arbitrary
    jump caused by rounding the number of tail observations and remains useful
    for small controlled scenario sets.
    """

    observations = np.sort(np.asarray(_return_series(returns), dtype=np.float64))
    confidence = _confidence(confidence_level)
    tail_mass_in_observations = _tail_observation_mass(
        confidence, len(observations)
    )
    whole_observations = int(tail_mass_in_observations)
    fractional_observation = tail_mass_in_observations - whole_observations

    weighted_sum = float(observations[:whole_observations].sum())
    if fractional_observation > 0.0:
        weighted_sum += (
            observations[whole_observations] * fractional_observation
        )
    return float(weighted_sum / tail_mass_in_observations)


def drawdown_series(returns: Iterable[Any]) -> tuple[float, ...]:
    """Return the signed drawdown after each simple-return observation.

    Wealth starts at 1.0, so a loss in the first period is measured from the
    initial capital rather than being incorrectly reported as zero.  Each
    result is at most zero and equals ``wealth / running_peak - 1``.
    """

    observations = np.asarray(_return_series(returns), dtype=np.float64)
    wealth = np.cumprod(1.0 + observations)
    running_peaks = np.maximum.accumulate(
        np.concatenate((np.asarray([1.0]), wealth))
    )[1:]
    return tuple((wealth / running_peaks - 1.0).tolist())


def maximum_drawdown(returns: Iterable[Any]) -> float:
    """Return maximum drawdown as a non-negative fraction of peak wealth."""

    return -min(drawdown_series(returns))


def calculate_historical_risk_metrics(
    returns: Iterable[Any], *, confidence_level: float = DEFAULT_CONFIDENCE_LEVEL
) -> HistoricalRiskMetrics:
    """Calculate VaR, expected shortfall and maximum drawdown together."""

    observations = _return_series(returns)
    confidence = _confidence(confidence_level)
    return HistoricalRiskMetrics(
        confidence_level=confidence,
        observation_count=len(observations),
        value_at_risk=value_at_risk(
            observations, confidence_level=confidence
        ),
        expected_shortfall=expected_shortfall(
            observations, confidence_level=confidence
        ),
        maximum_drawdown=maximum_drawdown(observations),
    )


def historical_risk_metrics_from_dataset(
    dataset: AlignedReturnDataset,
    symbol: str,
    *,
    confidence_level: float = DEFAULT_CONFIDENCE_LEVEL,
) -> HistoricalRiskMetrics:
    """Calculate all historical risk metrics for a named aligned series."""

    dataset = aligned_return_dataset(dataset)
    return calculate_historical_risk_metrics(
        dataset.returns_for(symbol), confidence_level=confidence_level
    )


# Explicit aliases make the methodology discoverable in application code.
historical_value_at_risk = value_at_risk
historical_expected_shortfall = expected_shortfall
historical_var = value_at_risk
calculate_var = value_at_risk
calculate_value_at_risk = value_at_risk
calculate_expected_shortfall = expected_shortfall
calculate_maximum_drawdown = maximum_drawdown
max_drawdown = maximum_drawdown


__all__ = [
    "DEFAULT_CONFIDENCE_LEVEL",
    "HistoricalRiskMetrics",
    "RiskMetricError",
    "calculate_historical_risk_metrics",
    "calculate_expected_shortfall",
    "calculate_maximum_drawdown",
    "calculate_value_at_risk",
    "calculate_var",
    "drawdown_series",
    "expected_shortfall",
    "historical_expected_shortfall",
    "historical_risk_metrics_from_dataset",
    "historical_var",
    "historical_value_at_risk",
    "max_drawdown",
    "maximum_drawdown",
    "value_at_risk",
]
