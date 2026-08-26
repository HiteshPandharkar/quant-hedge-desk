"""Calculation service that orchestrates a hedge-mandate assessment."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from quant_hedge_desk.analytics.concentration import calculate_concentration_metrics
from quant_hedge_desk.analytics.downside import downside_beta
from quant_hedge_desk.analytics.errors import ExposureMetricError
from quant_hedge_desk.analytics.exposure import market_beta, tracking_error
from quant_hedge_desk.analytics.returns import (
    build_aligned_return_dataset,
    build_available_weight_portfolio_returns,
)
from quant_hedge_desk.analytics.risk import (
    calculate_historical_risk_metrics,
    expected_shortfall,
    value_at_risk,
)
from quant_hedge_desk.application.constants import (
    ASSESSMENT_LIMITATIONS,
    BENCHMARK_SYMBOL_ALIASES,
    FEASIBILITY_PENDING_REASON,
    HEDGE_PENDING_REASON,
    SCENARIO_PENDING_REASON,
    TRADING_DAYS_PER_MONTH,
)
from quant_hedge_desk.application.enums import StageStatus
from quant_hedge_desk.application.errors import AssessmentInputError
from quant_hedge_desk.application.models import (
    HorizonRiskMetrics,
    IndexExposureMetrics,
    InputValidationSummary,
    MandateAssessment,
    MandateRiskComparison,
    MarketDataSummary,
    PendingStage,
    PortfolioSummary,
)
from quant_hedge_desk.data.constants import ADJUSTED_CLOSE_FIELD
from quant_hedge_desk.data.loaders import (
    load_portfolio_csv_with_report,
    load_yaml_mapping,
)
from quant_hedge_desk.data.repositories import (
    AdjustedCloseCSVRepository,
    AdjustedCloseRepository,
)
from quant_hedge_desk.domain.desk_limits import DeskLimitSet
from quant_hedge_desk.domain.mandate import Mandate


class MandateAssessmentService:
    """Load inputs and calculate all currently supported assessment stages.

    The market-data repository is injected so a database or remote adapter can
    replace the CSV implementation without changing the calculation workflow.
    """

    def __init__(
        self,
        *,
        market_data_repository: AdjustedCloseRepository | None = None,
        trading_days_per_month: int = TRADING_DAYS_PER_MONTH,
    ) -> None:
        if (
            isinstance(trading_days_per_month, bool)
            or not isinstance(trading_days_per_month, int)
            or trading_days_per_month <= 0
        ):
            raise ValueError("trading_days_per_month must be a positive integer")
        self._market_data_repository = (
            market_data_repository or AdjustedCloseCSVRepository()
        )
        self._trading_days_per_month = trading_days_per_month

    def assess(
        self,
        *,
        portfolio_path: str | Path,
        mandate_path: str | Path,
        desk_limits_path: str | Path,
        market_data_path: str | Path,
        supplied_total_market_value: Decimal | int | str | None = None,
    ) -> MandateAssessment:
        """Run implemented stages and return an immutable assessment."""

        portfolio_load = load_portfolio_csv_with_report(
            portfolio_path,
            supplied_total_market_value=supplied_total_market_value,
        )
        portfolio = portfolio_load.portfolio
        mandate = Mandate.from_mapping(load_yaml_mapping(mandate_path))
        desk_limits = DeskLimitSet.from_mapping(load_yaml_mapping(desk_limits_path))

        holding_symbols = tuple(holding.symbol for holding in portfolio.holdings)
        eligible_index_symbols = tuple(
            dict.fromkeys(
                underlying.value
                for underlying in mandate.client.eligibility.underlyings
            )
        )
        primary_benchmark = self._benchmark_symbol(mandate.client.benchmark)
        index_symbols = tuple(
            dict.fromkeys((primary_benchmark, *eligible_index_symbols))
        )
        required_symbols = (*holding_symbols, *index_symbols)

        price_history = self._market_data_repository.load(
            market_data_path,
            required_symbols=required_symbols,
            end_date=portfolio.as_of_date,
        )
        dataset = build_aligned_return_dataset(
            price_history,
            required_symbols=index_symbols,
        )
        portfolio_history = build_available_weight_portfolio_returns(
            price_history,
            {
                holding.symbol: holding.portfolio_weight
                for holding in portfolio.holdings
            },
            price_dates=dataset.price_dates,
        )
        portfolio_returns = portfolio_history.returns

        horizon_months = mandate.client.protection.horizon_months
        horizon_trading_days = horizon_months * self._trading_days_per_month
        horizon_returns = self._calculate_rolling_returns(
            portfolio_returns, horizon_trading_days
        )
        confidence = float(
            mandate.client.protection.expected_shortfall_confidence
        )
        loss_threshold = -float(mandate.client.protection.tail_loss_threshold)
        horizon_es = expected_shortfall(
            horizon_returns, confidence_level=confidence
        )
        signed_es_limit = -float(
            mandate.client.protection.max_expected_shortfall_loss
        )
        warnings = tuple(str(issue) for issue in portfolio_load.report.warnings)

        return MandateAssessment(
            mandate_id=mandate.mandate_id,
            desk_limits_id=desk_limits.desk_limits_id,
            input_validation=InputValidationSummary(
                StageStatus.COMPLETE, 0, len(warnings), warnings
            ),
            portfolio=PortfolioSummary(
                portfolio.portfolio_id,
                portfolio.as_of_date,
                len(portfolio.holdings),
                portfolio.total_market_value,
                mandate.client.reporting_currency,
                mandate.client.benchmark,
            ),
            market_data=MarketDataSummary(
                ADJUSTED_CLOSE_FIELD,
                dataset.price_dates[0],
                dataset.price_dates[-1],
                len(dataset.price_dates),
                dataset.observation_count,
                len(dataset.excluded_price_dates),
                required_symbols,
                "AVAILABLE_HOLDINGS_RENORMALIZED",
                portfolio_history.minimum_covered_weight,
                portfolio_history.incomplete_observation_count,
            ),
            concentration=calculate_concentration_metrics(portfolio),
            index_exposures=tuple(
                self._calculate_index_exposure(
                    symbol,
                    is_primary_benchmark=symbol == primary_benchmark,
                    portfolio_returns=portfolio_returns,
                    index_returns=dataset.returns_for(symbol),
                    horizon_trading_days=horizon_trading_days,
                )
                for symbol in index_symbols
            ),
            daily_risk=calculate_historical_risk_metrics(
                portfolio_returns, confidence_level=confidence
            ),
            horizon_risk=HorizonRiskMetrics(
                horizon_months,
                horizon_trading_days,
                len(horizon_returns),
                confidence,
                value_at_risk(horizon_returns, confidence_level=confidence),
                horizon_es,
                loss_threshold,
                float(np.mean(np.asarray(horizon_returns) < loss_threshold)),
                float(np.min(horizon_returns)),
                float(np.median(horizon_returns)),
                float(np.max(horizon_returns)),
            ),
            mandate_comparison=MandateRiskComparison(
                signed_es_limit,
                horizon_es,
                horizon_es - signed_es_limit,
                horizon_es >= signed_es_limit,
                mandate.client.protection.tail_breach_reduction_must_be_reported,
            ),
            scenario_assessment=PendingStage(
                StageStatus.NOT_ASSESSED, SCENARIO_PENDING_REASON
            ),
            hedge_assessment=PendingStage(
                StageStatus.NOT_ASSESSED, HEDGE_PENDING_REASON
            ),
            feasibility_assessment=PendingStage(
                StageStatus.NOT_ASSESSED, FEASIBILITY_PENDING_REASON
            ),
            limitations=ASSESSMENT_LIMITATIONS,
        )

    @staticmethod
    def _calculate_portfolio_returns(
        holding_symbols: Sequence[str],
        weights: Sequence[Decimal],
        aligned_returns: Mapping[str, tuple[float, ...]],
    ) -> tuple[float, ...]:
        weight_vector = np.fromiter(
            (float(weight) for weight in weights),
            dtype=np.float64,
            count=len(weights),
        )
        return_matrix = np.asarray(
            [aligned_returns[symbol] for symbol in holding_symbols],
            dtype=np.float64,
        )
        return tuple((weight_vector @ return_matrix).tolist())

    @staticmethod
    def _calculate_correlation(
        left: Iterable[float], right: Iterable[float]
    ) -> float:
        left_values = np.asarray(tuple(left), dtype=np.float64)
        right_values = np.asarray(tuple(right), dtype=np.float64)
        left_centered = left_values - left_values.mean()
        right_centered = right_values - right_values.mean()
        denominator = float(
            np.sqrt(np.dot(left_centered, left_centered) * np.dot(right_centered, right_centered))
        )
        if denominator == 0:
            raise AssessmentInputError(
                "correlation is undefined for a constant series"
            )
        return float(np.dot(left_centered, right_centered) / denominator)

    @staticmethod
    def _calculate_rolling_returns(
        returns: Sequence[float], horizon_trading_days: int
    ) -> tuple[float, ...]:
        if len(returns) < horizon_trading_days:
            raise AssessmentInputError(
                f"at least {horizon_trading_days} returns are required for the "
                "mandate horizon"
            )
        return_windows = sliding_window_view(
            np.asarray(returns, dtype=np.float64) + 1.0,
            horizon_trading_days,
        )
        return tuple((np.prod(return_windows, axis=1) - 1.0).tolist())

    @staticmethod
    def _calculate_rolling_beta_range(
        portfolio_returns: Sequence[float],
        index_returns: Sequence[float],
        horizon_trading_days: int,
    ) -> tuple[float, float]:
        portfolio_windows = sliding_window_view(
            np.asarray(portfolio_returns, dtype=np.float64),
            horizon_trading_days,
        )
        index_windows = sliding_window_view(
            np.asarray(index_returns, dtype=np.float64),
            horizon_trading_days,
        )
        portfolio_centered = portfolio_windows - portfolio_windows.mean(
            axis=1, keepdims=True
        )
        index_centered = index_windows - index_windows.mean(
            axis=1, keepdims=True
        )
        denominator = np.einsum("ij,ij->i", index_centered, index_centered)
        if np.any(denominator == 0):
            raise ExposureMetricError(
                "market beta is undefined for zero benchmark variance"
            )
        numerator = np.einsum(
            "ij,ij->i", portfolio_centered, index_centered
        )
        betas = numerator / denominator
        return float(betas.min()), float(betas.max())

    def _calculate_index_exposure(
        self,
        symbol: str,
        *,
        is_primary_benchmark: bool,
        portfolio_returns: Sequence[float],
        index_returns: Sequence[float],
        horizon_trading_days: int,
    ) -> IndexExposureMetrics:
        minimum_beta, maximum_beta = self._calculate_rolling_beta_range(
            portfolio_returns, index_returns, horizon_trading_days
        )
        return IndexExposureMetrics(
            symbol=symbol,
            is_primary_benchmark=is_primary_benchmark,
            beta=market_beta(portfolio_returns, index_returns),
            downside_beta=downside_beta(portfolio_returns, index_returns),
            correlation=self._calculate_correlation(
                portfolio_returns, index_returns
            ),
            annualized_tracking_error=tracking_error(
                portfolio_returns, index_returns
            ),
            rolling_horizon_beta_minimum=minimum_beta,
            rolling_horizon_beta_maximum=maximum_beta,
        )

    @staticmethod
    def _benchmark_symbol(benchmark_name: str) -> str:
        normalized = benchmark_name.strip().upper()
        return BENCHMARK_SYMBOL_ALIASES.get(normalized, normalized)


__all__ = ["MandateAssessmentService"]
