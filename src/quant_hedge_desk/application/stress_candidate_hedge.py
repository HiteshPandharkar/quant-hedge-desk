"""Programmatic facade for named correlation and liquidity stress testing."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Mapping, Sequence

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
from quant_hedge_desk.domain.models.portfolio import Portfolio
from quant_hedge_desk.domain.models.rebalancing import (
    CandidateStressBatchResult,
    RebalancingStressPolicy,
)
from quant_hedge_desk.domain.models.scenario_contracts import ScenarioSet
from quant_hedge_desk.hedge_design.candidate_generator import HedgeCandidate
from quant_hedge_desk.hedge_design.stress_evaluator import (
    CandidateStressEvaluation,
    evaluate_candidate_stresses,
)
from quant_hedge_desk.scenarios.manual_generator import ManualScenarioGenerator


@dataclass(frozen=True, slots=True)
class _StressInputs:
    portfolio: Portfolio
    mandate: Mandate
    scenario_set: ScenarioSet
    basis_limit: Decimal | str
    policy: RebalancingStressPolicy | None
    portfolio_horizon_returns: Sequence[float] | None
    underlying_horizon_returns: Mapping[str, Sequence[float]] | None


def _validate_common_arguments(
    *,
    rebalancing_policy_path: str | Path | None,
    market_data_path: str | Path | None,
    trading_days_per_month: int,
) -> None:
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


def _load_stress_inputs(
    *,
    portfolio_path: str | Path,
    mandate_path: str | Path,
    stress_scenario_path: str | Path,
    supplied_total_market_value: Decimal | int | str | None,
    maximum_correlation_basis_gap: Decimal | str | None,
    rebalancing_policy_path: str | Path | None,
    market_data_path: str | Path | None,
    trading_days_per_month: int,
) -> _StressInputs:
    _validate_common_arguments(
        rebalancing_policy_path=rebalancing_policy_path,
        market_data_path=market_data_path,
        trading_days_per_month=trading_days_per_month,
    )
    portfolio = load_portfolio_csv(
        portfolio_path, supplied_total_market_value=supplied_total_market_value
    )
    mandate = Mandate.from_mapping(load_yaml_mapping(mandate_path))
    scenario_set = ManualScenarioGenerator.from_mapping(
        load_yaml_mapping(stress_scenario_path)
    ).generate()
    basis_limit = (
        scenario_set.parameters.get("maximum_correlation_basis_gap", "0.05")
        if maximum_correlation_basis_gap is None
        else maximum_correlation_basis_gap
    )
    if rebalancing_policy_path is None:
        return _StressInputs(
            portfolio,
            mandate,
            scenario_set,
            basis_limit,
            None,
            None,
            None,
        )

    assert market_data_path is not None
    policy = load_rebalancing_stress_policy(rebalancing_policy_path)
    holding_symbols = tuple(item.symbol for item in portfolio.holdings)
    eligible_symbols = tuple(
        dict.fromkeys(item.value for item in mandate.client.eligibility.underlyings)
    )
    history = AdjustedCloseCSVRepository().load(
        market_data_path,
        required_symbols=(*holding_symbols, *eligible_symbols),
        end_date=portfolio.as_of_date,
    )
    dataset = build_aligned_return_dataset(history, required_symbols=eligible_symbols)
    portfolio_history = build_available_weight_portfolio_returns(
        history,
        {
            holding.symbol: holding.portfolio_weight
            for holding in portfolio.holdings
        },
        price_dates=dataset.price_dates,
    )
    horizon = mandate.client.protection.horizon_months * trading_days_per_month
    return _StressInputs(
        portfolio,
        mandate,
        scenario_set,
        basis_limit,
        policy,
        _rolling_returns(portfolio_history.returns, horizon),
        {
            symbol: _rolling_returns(dataset.returns_for(symbol), horizon)
            for symbol in eligible_symbols
        },
    )


def _evaluate_candidate(
    candidate: HedgeCandidate, inputs: _StressInputs
) -> CandidateStressEvaluation:
    underlying_returns = inputs.underlying_horizon_returns
    if underlying_returns is not None:
        candidate_symbols = tuple(
            dict.fromkeys(leg.underlying.value for leg in candidate.legs)
        )
        underlying_returns = {
            symbol: underlying_returns[symbol] for symbol in candidate_symbols
        }
    return evaluate_candidate_stresses(
        scenario_set=inputs.scenario_set,
        portfolio=inputs.portfolio,
        candidate=candidate,
        mandate=inputs.mandate,
        maximum_correlation_basis_gap=inputs.basis_limit,
        rebalancing_policy=inputs.policy,
        portfolio_horizon_returns=inputs.portfolio_horizon_returns,
        underlying_horizon_returns=underlying_returns,
    )


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

    _validate_common_arguments(
        rebalancing_policy_path=rebalancing_policy_path,
        market_data_path=market_data_path,
        trading_days_per_month=trading_days_per_month,
    )
    candidate = HedgeCandidate.from_mapping(load_yaml_mapping(candidate_path))
    inputs = _load_stress_inputs(
        portfolio_path=portfolio_path,
        mandate_path=mandate_path,
        stress_scenario_path=stress_scenario_path,
        supplied_total_market_value=supplied_total_market_value,
        maximum_correlation_basis_gap=maximum_correlation_basis_gap,
        rebalancing_policy_path=rebalancing_policy_path,
        market_data_path=market_data_path,
        trading_days_per_month=trading_days_per_month,
    )
    return _evaluate_candidate(candidate, inputs)


def stress_candidate_hedges(
    *,
    portfolio_path: str | Path,
    mandate_path: str | Path,
    candidate_paths: Iterable[str | Path],
    stress_scenario_path: str | Path,
    rebalancing_policy_path: str | Path,
    market_data_path: str | Path,
    supplied_total_market_value: Decimal | int | str | None = None,
    maximum_correlation_basis_gap: Decimal | str | None = None,
    trading_days_per_month: int = 21,
) -> CandidateStressBatchResult:
    """Stress multiple candidates against one shared, versioned input set.

    Configuration and historical data are loaded once. Invalid input aborts the
    call, while a valid candidate that fails a stress remains an ordinary
    structured evaluation in ``rejected_candidate_ids``.
    """

    _validate_common_arguments(
        rebalancing_policy_path=rebalancing_policy_path,
        market_data_path=market_data_path,
        trading_days_per_month=trading_days_per_month,
    )
    if isinstance(candidate_paths, (str, bytes, Path)):
        raise TypeError("candidate_paths must be an iterable of paths, not one path")
    paths = tuple(candidate_paths)
    if not paths:
        raise ValueError("candidate_paths must be non-empty")

    # Parse every candidate before expensive shared market-data preparation so
    # malformed files and duplicate public identities fail fast.
    candidates = tuple(
        HedgeCandidate.from_mapping(load_yaml_mapping(path)) for path in paths
    )
    candidate_ids = tuple(item.candidate_id for item in candidates)
    duplicates = sorted(
        {item for item in candidate_ids if candidate_ids.count(item) > 1}
    )
    if duplicates:
        raise ValueError("duplicate candidate_ids: " + ", ".join(duplicates))

    inputs = _load_stress_inputs(
        portfolio_path=portfolio_path,
        mandate_path=mandate_path,
        stress_scenario_path=stress_scenario_path,
        supplied_total_market_value=supplied_total_market_value,
        maximum_correlation_basis_gap=maximum_correlation_basis_gap,
        rebalancing_policy_path=rebalancing_policy_path,
        market_data_path=market_data_path,
        trading_days_per_month=trading_days_per_month,
    )
    assert inputs.policy is not None
    evaluations = tuple(
        _evaluate_candidate(candidate, inputs) for candidate in candidates
    )
    return CandidateStressBatchResult(
        scenario_set_id=inputs.scenario_set.scenario_set_id,
        scenario_set_version=inputs.scenario_set.version,
        policy_id=inputs.policy.policy_id,
        policy_version=inputs.policy.version,
        evaluations=evaluations,
        releasable_candidate_ids=tuple(
            item.candidate_id for item in evaluations if item.passed
        ),
        rejected_candidate_ids=tuple(
            item.candidate_id for item in evaluations if not item.passed
        ),
    )


__all__ = ["stress_candidate_hedge", "stress_candidate_hedges"]
