"""Immutable request-independent results produced by mandate assessment."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from quant_hedge_desk.analytics.models import ConcentrationMetrics, HistoricalRiskMetrics
from quant_hedge_desk.application.enums import StageStatus
from quant_hedge_desk.serialization import json_ready


@dataclass(frozen=True, slots=True)
class InputValidationSummary:
    status: StageStatus
    error_count: int
    warning_count: int
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PortfolioSummary:
    portfolio_id: str
    as_of_date: date
    holding_count: int
    total_market_value: Decimal
    reporting_currency: str
    benchmark: str


@dataclass(frozen=True, slots=True)
class MarketDataSummary:
    price_field: str
    common_start_date: date
    common_end_date: date
    aligned_price_count: int
    return_observation_count: int
    excluded_union_date_count: int
    symbols: tuple[str, ...]
    portfolio_return_method: str = "FULL_INTERSECTION_FIXED_WEIGHT"
    minimum_covered_weight: float = 1.0
    incomplete_weight_observation_count: int = 0


@dataclass(frozen=True, slots=True)
class IndexExposureMetrics:
    symbol: str
    is_primary_benchmark: bool
    beta: float
    downside_beta: float
    correlation: float
    annualized_tracking_error: float
    rolling_horizon_beta_minimum: float
    rolling_horizon_beta_maximum: float


@dataclass(frozen=True, slots=True)
class HorizonRiskMetrics:
    horizon_months: int
    horizon_trading_days: int
    overlapping_window_count: int
    confidence_level: float
    value_at_risk: float
    expected_shortfall: float
    tail_loss_threshold: float
    tail_breach_probability: float
    worst_return: float
    median_return: float
    best_return: float


@dataclass(frozen=True, slots=True)
class MandateRiskComparison:
    signed_expected_shortfall_limit: float
    unhedged_expected_shortfall: float
    margin_to_limit: float
    point_estimate_within_limit: bool
    requires_tail_breach_reduction_report: bool


@dataclass(frozen=True, slots=True)
class PendingStage:
    status: StageStatus
    reason: str


@dataclass(frozen=True, slots=True)
class MandateAssessment:
    """Structured result returned to CLI, API, and reporting adapters."""

    mandate_id: str
    desk_limits_id: str
    input_validation: InputValidationSummary
    portfolio: PortfolioSummary
    market_data: MarketDataSummary
    concentration: ConcentrationMetrics
    index_exposures: tuple[IndexExposureMetrics, ...]
    daily_risk: HistoricalRiskMetrics
    horizon_risk: HorizonRiskMetrics
    mandate_comparison: MandateRiskComparison
    scenario_assessment: PendingStage
    hedge_assessment: PendingStage
    feasibility_assessment: PendingStage
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready dictionary without losing Decimal precision."""

        return json_ready(asdict(self))


__all__ = [
    "HorizonRiskMetrics",
    "IndexExposureMetrics",
    "InputValidationSummary",
    "MandateAssessment",
    "MandateRiskComparison",
    "MarketDataSummary",
    "PendingStage",
    "PortfolioSummary",
]
