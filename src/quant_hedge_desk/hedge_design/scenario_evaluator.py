"""Orchestrate candidate valuation on a versioned scenario set."""

from __future__ import annotations

from decimal import Decimal

from quant_hedge_desk.domain.models.portfolio import Portfolio
from quant_hedge_desk.domain.models.scenario_contracts import ScenarioSet
from quant_hedge_desk.domain.models.scenario_outcomes import (
    ScenarioEvaluation,
    ScenarioOutcome,
)
from quant_hedge_desk.hedge_design.candidate_generator import HedgeCandidate
from quant_hedge_desk.hedge_design.scenario_calculations import (
    all_in_hedge_cost,
    calculate_scenario_outcome,
    positive_fraction,
    tail_breach_probability,
)


def evaluate_scenario_outcomes(
    *,
    scenario_set: ScenarioSet,
    portfolio: Portfolio,
    candidate: HedgeCandidate,
    tail_loss_threshold: Decimal | str = Decimal("0.10"),
) -> ScenarioEvaluation:
    """Calculate unhedged and hedged terminal outcomes for every scenario.

    Scenario paths must supply every underlying referenced by the candidate.
    Portfolio performance may be supplied directly under ``PORTFOLIO`` (useful
    for named stresses), or derived from all holding symbols and inception
    weights (useful for generated historical/bootstrap paths).
    """

    if not isinstance(scenario_set, ScenarioSet):
        raise TypeError("scenario_set must be a ScenarioSet")
    if not isinstance(portfolio, Portfolio):
        raise TypeError("portfolio must be a Portfolio")
    if not isinstance(candidate, HedgeCandidate):
        raise TypeError("candidate must be a HedgeCandidate")

    threshold = positive_fraction(tail_loss_threshold, "tail_loss_threshold")
    underlying_symbols = {leg.underlying.value for leg in candidate.legs}
    available_symbols = set(scenario_set.symbols)
    missing = sorted(underlying_symbols - available_symbols)
    if missing:
        raise ValueError(
            "scenario set is missing required returns: " + ", ".join(missing)
        )
    if "PORTFOLIO" not in available_symbols:
        holding_symbols = {holding.symbol for holding in portfolio.holdings}
        missing_holdings = sorted(holding_symbols - available_symbols)
        if missing_holdings:
            raise ValueError(
                "scenario set must contain PORTFOLIO or all holding returns; "
                "missing holdings: " + ", ".join(missing_holdings)
            )

    all_in_cost = all_in_hedge_cost(candidate)
    outcomes = tuple(
        calculate_scenario_outcome(
            scenario=scenario,
            probability=probability,
            portfolio=portfolio,
            candidate=candidate,
            underlying_symbols=underlying_symbols,
            all_in_hedge_cost=all_in_cost,
        )
        for scenario, probability in zip(
            scenario_set.scenarios, scenario_set.probability_weights
        )
    )
    return ScenarioEvaluation(
        scenario_set_id=scenario_set.scenario_set_id,
        scenario_set_version=scenario_set.version,
        methodology=scenario_set.methodology.value,
        model_version=scenario_set.model_version,
        candidate_id=candidate.candidate_id,
        portfolio_id=portfolio.portfolio_id,
        initial_portfolio_value=portfolio.total_market_value,
        all_in_hedge_cost=all_in_cost,
        tail_loss_threshold=threshold,
        unhedged_tail_breach_probability=tail_breach_probability(
            outcomes,
            threshold=threshold,
            return_value=lambda outcome: outcome.portfolio_return,
        ),
        hedged_tail_breach_probability=tail_breach_probability(
            outcomes,
            threshold=threshold,
            return_value=lambda outcome: outcome.hedged_return,
        ),
        outcomes=outcomes,
    )


__all__ = [
    "ScenarioEvaluation",
    "ScenarioOutcome",
    "evaluate_scenario_outcomes",
]
