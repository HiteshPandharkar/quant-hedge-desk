"""Programmatic facade for named correlation and liquidity stress testing."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from quant_hedge_desk.analytics.returns import (
    build_aligned_return_dataset,
    build_available_weight_portfolio_returns,
)
from quant_hedge_desk.application.assess_candidate_hedge import _rolling_returns
from quant_hedge_desk.data.loaders import (
    load_portfolio_csv,
    load_rebalancing_stress_policy,
    load_yaml_mapping,
)
from quant_hedge_desk.data.repositories import AdjustedCloseCSVRepository
from quant_hedge_desk.domain.mandate import Mandate
from quant_hedge_desk.hedge_design.candidate_generator import HedgeCandidate
from quant_hedge_desk.hedge_design.stress_evaluator import (
    CandidateStressEvaluation,
    evaluate_candidate_stresses,
)
from quant_hedge_desk.scenarios.manual_generator import ManualScenarioGenerator


def stress_candidate_hedge(
    *,
    portfolio_path: str | Path,
    mandate_path: str | Path,
    candidate_path: str | Path,
    stress_scenario_path: str | Path,
    supplied_total_market_value: Decimal | int | str | None = None,
    maximum_correlation_basis_gap: Decimal | str | None = None,
    rebalancing_policy_path: str | Path | None = None,
    market_data_path: str | Path | None = None,
    trading_days_per_month: int = 21,
) -> CandidateStressEvaluation:
    """Evaluate static stresses and, when configured, sequential rebalancing.

    ``market_data_path`` is required only with a rebalancing policy because
    accepted fills must be checked against the mandate using historical
    horizon returns. Calls using the original arguments retain static behavior.
    """

    if (rebalancing_policy_path is None) != (market_data_path is None):
        raise ValueError(
            "rebalancing_policy_path and market_data_path must be supplied together"
        )
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
    scenario_set = ManualScenarioGenerator.from_mapping(
        load_yaml_mapping(stress_scenario_path)
    ).generate()
    basis_limit = (
        scenario_set.parameters.get("maximum_correlation_basis_gap", "0.05")
        if maximum_correlation_basis_gap is None
        else maximum_correlation_basis_gap
    )
    policy = None
    portfolio_horizon_returns = None
    underlying_horizon_returns = None
    if rebalancing_policy_path is not None:
        assert market_data_path is not None
        policy = load_rebalancing_stress_policy(rebalancing_policy_path)
        holding_symbols = tuple(item.symbol for item in portfolio.holdings)
        eligible_symbols = tuple(
            dict.fromkeys(
                item.value for item in mandate.client.eligibility.underlyings
            )
        )
        candidate_symbols = tuple(
            dict.fromkeys(leg.underlying.value for leg in candidate.legs)
        )
        history = AdjustedCloseCSVRepository().load(
            market_data_path,
            required_symbols=(*holding_symbols, *eligible_symbols),
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
        horizon = mandate.client.protection.horizon_months * trading_days_per_month
        portfolio_horizon_returns = _rolling_returns(
            portfolio_history.returns, horizon
        )
        underlying_horizon_returns = {
            symbol: _rolling_returns(dataset.returns_for(symbol), horizon)
            for symbol in candidate_symbols
        }
    return evaluate_candidate_stresses(
        scenario_set=scenario_set,
        portfolio=portfolio,
        candidate=candidate,
        mandate=mandate,
        maximum_correlation_basis_gap=basis_limit,
        rebalancing_policy=policy,
        portfolio_horizon_returns=portfolio_horizon_returns,
        underlying_horizon_returns=underlying_horizon_returns,
    )


__all__ = ["stress_candidate_hedge"]
