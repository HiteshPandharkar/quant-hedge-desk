"""Shared statistical kernels used by multiple analytics modules."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def ols_slope(
    response: Sequence[float],
    predictor: Sequence[float],
    *,
    error_type: type[ValueError],
    zero_variance_message: str,
) -> float:
    """Return the OLS slope with an intercept for an aligned pair."""

    response_values = np.asarray(response, dtype=np.float64)
    predictor_values = np.asarray(predictor, dtype=np.float64)
    response_centered = response_values - response_values.mean()
    predictor_centered = predictor_values - predictor_values.mean()
    predictor_sum_squares = float(np.dot(predictor_centered, predictor_centered))
    if predictor_sum_squares == 0:
        raise error_type(zero_variance_message)
    covariance_sum = float(np.dot(response_centered, predictor_centered))
    return covariance_sum / predictor_sum_squares
