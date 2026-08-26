"""Programmatic facade for assessing a configured hedge candidate."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from quant_hedge_desk.analytics.returns import (
    build_aligned_return_dataset,
    build_available_weight_portfolio_returns,
)
from quant_hedge_desk.data.loaders import load_portfolio_csv, load_yaml_mapping
from quant_hedge_desk.data.repositories import AdjustedCloseCSVRepository
from quant_hedge_desk.domain.mandate import Mandate
from quant_hedge_desk.hedge_design.candidate_generator import HedgeCandidate
from quant_hedge_desk.hedge_design.constraint_calculator import (
    CandidateConstraintCalculator,
)
from quant_hedge_desk.hedge_design.constraint_models import (
    CandidateFeasibilityAssessment,
)
from quant_hedge_desk.pricing.ports import PricingAdapter


def _rolling_returns(values: tuple[float, ...], horizon: int) -> tuple[float, ...]:
    windows = sliding_window_view(np.asarray(values, dtype=np.float64) + 1.0, horizon)
    return tuple((np.prod(windows, axis=1) - 1.0).tolist())


def assess_candidate_hedge(
    *,
    portfolio_path: str | Path,
    mandate_path: str | Path,
    candidate_path: str | Path,
    market_data_path: str | Path,
    supplied_total_market_value: Decimal | int | str | None = None,
    trading_days_per_month: int = 21,
    pricing_adapter: PricingAdapter | None = None,
    max_quote_age: timedelta | None = None,
) -> CandidateFeasibilityAssessment:
    """Load inputs, optionally reprice the candidate, and evaluate every hard rule."""

    if (
        isinstance(trading_days_per_month, bool)
        or not isinstance(trading_days_per_month, int)
        or trading_days_per_month <= 0
    ):
        raise ValueError("trading_days_per_month must be a positive integer")
    portfolio = load_portfolio_csv(
        portfolio_path, supplied_total_market_value=supplied_total_market_value
    )
    mandate = Mandate.from_mapping(load_yaml_mapping(mandate_path))
    candidate = HedgeCandidate.from_mapping(load_yaml_mapping(candidate_path))
    if max_quote_age is not None and pricing_adapter is None:
        raise ValueError("max_quote_age requires a pricing_adapter")
    if pricing_adapter is not None:
        candidate = pricing_adapter.price_candidate(candidate, max_age=max_quote_age)
    horizon = mandate.client.protection.horizon_months * trading_days_per_month
    holding_symbols = tuple(item.symbol for item in portfolio.holdings)
    candidate_symbols = tuple(dict.fromkeys(leg.underlying.value for leg in candidate.legs))
    # Align every candidate on the same mandate-wide index history so rankings
    # cannot change merely because one structure uses fewer underlyings.
    eligible_symbols = tuple(
        dict.fromkeys(item.value for item in mandate.client.eligibility.underlyings)
    )
    required_symbols = (*holding_symbols, *eligible_symbols)
    history = AdjustedCloseCSVRepository().load(
        market_data_path,
        required_symbols=required_symbols,
        end_date=portfolio.as_of_date,
    )
    dataset = build_aligned_return_dataset(
        history, required_symbols=eligible_symbols
    )
    portfolio_history = build_available_weight_portfolio_returns(
        history,
        {
            holding.symbol: holding.portfolio_weight
            for holding in portfolio.holdings
        },
        price_dates=dataset.price_dates,
    )
    daily_portfolio_returns = portfolio_history.returns
    return CandidateConstraintCalculator(
        candidate=candidate,
        mandate=mandate,
        portfolio=portfolio,
        portfolio_horizon_returns=_rolling_returns(daily_portfolio_returns, horizon),
        underlying_horizon_returns={
            symbol: _rolling_returns(dataset.returns_for(symbol), horizon)
            for symbol in candidate_symbols
        },
    ).assess()


__all__ = ["assess_candidate_hedge"]
