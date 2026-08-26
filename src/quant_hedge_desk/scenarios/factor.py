"""Parametric factor-simulation scenarios fitted to aligned daily returns."""

from __future__ import annotations

from datetime import date
from math import isfinite
from typing import Iterable

import numpy as np

from quant_hedge_desk.analytics._validation import positive_integer
from quant_hedge_desk.analytics.models import AlignedReturnDataset
from quant_hedge_desk.domain.enums import ScenarioMethodology
from quant_hedge_desk.domain.errors import ScenarioValidationError
from quant_hedge_desk.domain.models.scenario_contracts import (
    ScenarioPath,
    ScenarioSet,
    ScenarioStep,
)
from quant_hedge_desk.domain.scenario_validation import scenario_date


DEFAULT_FACTOR_SIMULATION_MODEL_VERSION = "gaussian-log-return-factor-model/1.0"


class FactorSimulationScenarioGenerator:
    """Simulate paths from a factor model estimated on aligned observations.

    Historical simple returns are transformed to log returns. Factor means and
    covariance are estimated directly, while each non-factor symbol is fitted
    by OLS to an intercept and the factor log returns. Simulated non-factor
    returns add an independent Gaussian residual using the fitted sample
    residual volatility. Converting simulated log returns with ``expm1`` keeps
    every generated simple return strictly above -100%.

    The generator deliberately uses a fresh NumPy random generator for every
    call. A configured seed therefore makes generation reproducible without
    changing process-wide random state.
    """

    __slots__ = (
        "_as_of_date",
        "_dataset",
        "_factor_symbols",
        "_horizon_trading_days",
        "_model_version",
        "_random_seed",
        "_scenario_count",
        "_scenario_set_id",
        "_source_snapshot_ids",
        "_version",
    )

    def __init__(
        self,
        *,
        scenario_set_id: str,
        version: str,
        as_of_date: date | str,
        horizon_trading_days: int,
        dataset: AlignedReturnDataset,
        factor_symbols: Iterable[str],
        scenario_count: int,
        random_seed: int | None = None,
        model_version: str = DEFAULT_FACTOR_SIMULATION_MODEL_VERSION,
        source_snapshot_ids: Iterable[str] = (),
    ) -> None:
        if not isinstance(dataset, AlignedReturnDataset):
            raise ScenarioValidationError("dataset must be an AlignedReturnDataset")
        positive_integer(
            horizon_trading_days,
            "horizon_trading_days",
            error_type=ScenarioValidationError,
        )
        positive_integer(
            scenario_count,
            "scenario_count",
            error_type=ScenarioValidationError,
        )
        if isinstance(factor_symbols, (str, bytes)):
            raise ScenarioValidationError("factor_symbols must be an iterable of symbols")
        factors = tuple(str(item).strip().upper() for item in factor_symbols)
        if not factors or any(not item for item in factors):
            raise ScenarioValidationError("factor_symbols must be non-empty")
        if len(set(factors)) != len(factors):
            raise ScenarioValidationError("factor_symbols must be unique")
        missing = tuple(item for item in factors if item not in dataset.symbols)
        if missing:
            raise ScenarioValidationError(
                "factor_symbols are absent from dataset: " + ", ".join(missing)
            )
        minimum_observations = len(factors) + 2
        if dataset.observation_count < minimum_observations:
            raise ScenarioValidationError(
                f"dataset needs at least {minimum_observations} observations "
                "to estimate factor exposures and residual risk"
            )
        if isinstance(random_seed, bool) or (
            random_seed is not None and not isinstance(random_seed, int)
        ):
            raise ScenarioValidationError("random_seed must be an integer or None")

        normalized_as_of_date = scenario_date(as_of_date, "as_of_date")
        if dataset.dates[-1] > normalized_as_of_date:
            raise ScenarioValidationError("dataset contains returns after as_of_date")

        return_matrix = np.column_stack(
            [np.asarray(dataset.returns[symbol], dtype=float) for symbol in dataset.symbols]
        )
        if np.any(return_matrix <= -1.0):
            raise ScenarioValidationError(
                "dataset simple returns must be greater than -1 for log transformation"
            )
        factor_log_returns = np.log1p(
            np.column_stack(
                [np.asarray(dataset.returns[symbol], dtype=float) for symbol in factors]
            )
        )
        design = np.column_stack(
            [np.ones(dataset.observation_count), factor_log_returns]
        )
        if np.linalg.matrix_rank(design) < design.shape[1]:
            raise ScenarioValidationError("historical factor design matrix is rank deficient")

        self._scenario_set_id = scenario_set_id
        self._version = version
        self._as_of_date = normalized_as_of_date
        self._horizon_trading_days = horizon_trading_days
        self._dataset = dataset
        self._factor_symbols = factors
        self._scenario_count = scenario_count
        self._random_seed = random_seed
        self._model_version = model_version
        self._source_snapshot_ids = tuple(source_snapshot_ids)

    def generate(self) -> ScenarioSet:
        """Return equally weighted paths from the fitted factor distribution."""

        factor_log_returns = np.log1p(
            np.column_stack(
                [
                    np.asarray(self._dataset.returns[symbol], dtype=float)
                    for symbol in self._factor_symbols
                ]
            )
        )
        factor_mean = np.mean(factor_log_returns, axis=0)
        factor_covariance = np.atleast_2d(
            np.cov(factor_log_returns, rowvar=False, ddof=1)
        )
        design = np.column_stack(
            [np.ones(self._dataset.observation_count), factor_log_returns]
        )

        coefficients: dict[str, np.ndarray] = {}
        residual_volatilities: dict[str, float] = {}
        for symbol in self._dataset.symbols:
            if symbol in self._factor_symbols:
                continue
            target = np.log1p(np.asarray(self._dataset.returns[symbol], dtype=float))
            fitted, _, _, _ = np.linalg.lstsq(design, target, rcond=None)
            residuals = target - design @ fitted
            degrees_of_freedom = self._dataset.observation_count - design.shape[1]
            residual_variance = float(residuals @ residuals / degrees_of_freedom)
            coefficients[symbol] = fitted
            residual_volatilities[symbol] = residual_variance**0.5

        random = np.random.default_rng(self._random_seed)
        scenarios = tuple(
            self._build_path(
                scenario_number,
                random,
                factor_mean,
                factor_covariance,
                coefficients,
                residual_volatilities,
            )
            for scenario_number in range(1, self._scenario_count + 1)
        )
        parameters: dict[str, str | int | bool] = {
            "distribution": "multivariate_normal_log_returns",
            "estimation_method": "ols_with_independent_gaussian_residuals",
            "scenario_count": self._scenario_count,
            "factor_count": len(self._factor_symbols),
            "factor_symbols": ",".join(self._factor_symbols),
            "source_observation_count": self._dataset.observation_count,
        }
        if self._random_seed is not None:
            parameters["random_seed"] = self._random_seed

        return ScenarioSet(
            scenario_set_id=self._scenario_set_id,
            version=self._version,
            methodology=ScenarioMethodology.FACTOR_SIMULATION,
            as_of_date=self._as_of_date,
            horizon_trading_days=self._horizon_trading_days,
            scenarios=scenarios,
            model_version=self._model_version,
            parameters=parameters,
            source_snapshot_ids=self._source_snapshot_ids,
        )

    def _build_path(
        self,
        scenario_number: int,
        random: np.random.Generator,
        factor_mean: np.ndarray,
        factor_covariance: np.ndarray,
        coefficients: dict[str, np.ndarray],
        residual_volatilities: dict[str, float],
    ) -> ScenarioPath:
        factor_draws = random.multivariate_normal(
            factor_mean,
            factor_covariance,
            size=self._horizon_trading_days,
            check_valid="raise",
        )
        factor_draws = np.asarray(factor_draws).reshape(
            self._horizon_trading_days, len(self._factor_symbols)
        )
        simulated: dict[str, np.ndarray] = {
            symbol: factor_draws[:, index]
            for index, symbol in enumerate(self._factor_symbols)
        }
        augmented_factors = np.column_stack(
            [np.ones(self._horizon_trading_days), factor_draws]
        )
        for symbol, fitted in coefficients.items():
            residuals = random.normal(
                0.0,
                residual_volatilities[symbol],
                size=self._horizon_trading_days,
            )
            simulated[symbol] = augmented_factors @ fitted + residuals

        steps = tuple(
            ScenarioStep(
                step_number=step_number,
                asset_returns={
                    symbol: str(float(np.expm1(simulated[symbol][step_number - 1])))
                    for symbol in self._dataset.symbols
                },
            )
            for step_number in range(1, self._horizon_trading_days + 1)
        )
        if any(
            not isfinite(float(value))
            for step in steps
            for value in step.asset_returns.values()
        ):
            raise ScenarioValidationError("factor simulation produced a non-finite return")
        return ScenarioPath(
            scenario_id=f"factor-simulation-{scenario_number:06d}",
            name=f"Factor simulation scenario {scenario_number}",
            description=(
                f"{self._horizon_trading_days}-day path from a fitted Gaussian "
                f"log-return model with factors {', '.join(self._factor_symbols)}."
            ),
            steps=steps,
        )


__all__ = [
    "DEFAULT_FACTOR_SIMULATION_MODEL_VERSION",
    "FactorSimulationScenarioGenerator",
]
