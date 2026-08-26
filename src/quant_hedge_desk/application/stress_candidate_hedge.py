"""Programmatic facade for named correlation and liquidity stress testing."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from quant_hedge_desk.data.loaders import load_portfolio_csv, load_yaml_mapping
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
) -> CandidateStressEvaluation:
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
    return evaluate_candidate_stresses(
        scenario_set=scenario_set,
        portfolio=portfolio,
        candidate=candidate,
        mandate=mandate,
        maximum_correlation_basis_gap=basis_limit,
    )


__all__ = ["stress_candidate_hedge"]
