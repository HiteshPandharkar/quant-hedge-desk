"""Release-gate stresses for hedge correlation basis and executable liquidity."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from quant_hedge_desk.domain.enums import LegDirection, OptionType
from quant_hedge_desk.domain.models.derivative_legs import FutureLeg, VanillaOptionLeg
from quant_hedge_desk.domain.models.mandate import Mandate
from quant_hedge_desk.domain.models.portfolio import Portfolio
from quant_hedge_desk.domain.models.scenario_contracts import ScenarioPath, ScenarioSet
from quant_hedge_desk.hedge_design.candidate_generator import HedgeCandidate
from quant_hedge_desk.hedge_design.scenario_evaluator import evaluate_scenario_outcomes
from quant_hedge_desk.serialization import json_ready


@dataclass(frozen=True, slots=True)
class CandidateStressOutcome:
    scenario_id: str
    scenario_name: str
    portfolio_return: Decimal
    hedge_proxy_return: Decimal
    correlation_basis_gap: Decimal
    absolute_correlation_basis_gap: Decimal
    correlation_pass: bool
    baseline_execution_cost: Decimal
    stressed_execution_cost: Decimal
    stressed_all_in_cost: Decimal
    stressed_all_in_cost_fraction: Decimal
    cost_budget_pass: bool
    stressed_unwind_days: Decimal
    liquidity_inputs_valid: bool
    liquidity_pass: bool
    baseline_hedged_return: Decimal
    stressed_hedged_return: Decimal
    return_improvement: Decimal
    passed: bool


@dataclass(frozen=True, slots=True)
class CandidateStressEvaluation:
    scenario_set_id: str
    scenario_set_version: str
    candidate_id: str
    portfolio_id: str
    maximum_correlation_basis_gap: Decimal
    outcomes: tuple[CandidateStressOutcome, ...]
    passed: bool
    usage_restrictions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return json_ready(asdict(self))


def _decimal(value: object) -> Decimal | None:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return result if result.is_finite() else None


def _reference_notional(candidate: HedgeCandidate, leg: object) -> Decimal:
    return (
        candidate.initial_levels[leg.underlying.value]
        * leg.quantity
        * leg.contract_multiplier
    )


def _proxy_weights(candidate: HedgeCandidate) -> dict[str, Decimal]:
    notionals: dict[str, Decimal] = {}
    for leg in candidate.legs:
        protective = (
            isinstance(leg, FutureLeg) and leg.direction is LegDirection.SHORT
        ) or (
            isinstance(leg, VanillaOptionLeg)
            and leg.direction is LegDirection.LONG
            and leg.option_type is OptionType.PUT
        )
        if protective:
            symbol = leg.underlying.value
            notionals[symbol] = notionals.get(symbol, Decimal("0")) + _reference_notional(
                candidate, leg
            )
    total = sum(notionals.values(), Decimal("0"))
    if total <= 0:
        raise ValueError("candidate has no protective reference notional")
    return {symbol: amount / total for symbol, amount in notionals.items()}


def _path_multiplier(
    scenario: ScenarioPath, symbol: str, attribute: str, *, use_minimum: bool
) -> Decimal:
    values = [
        getattr(step, attribute).get(symbol, Decimal("1"))
        for step in scenario.steps
    ]
    return min(values) if use_minimum else max(values)


def evaluate_candidate_stresses(
    *,
    scenario_set: ScenarioSet,
    portfolio: Portfolio,
    candidate: HedgeCandidate,
    mandate: Mandate,
    maximum_correlation_basis_gap: Decimal | str = Decimal("0.05"),
) -> CandidateStressEvaluation:
    """Stress basis dislocation, bid-ask cost and executable unwind capacity.

    The hedge proxy is weighted by protective reference notional. Stressed
    execution cost allocates the candidate's aggregate baseline cost across all
    legs by gross reference notional, then applies each underlying's worst
    spread multiplier. Unwind capacity uses each underlying's worst market-
    volume multiplier across the path.
    """

    if not isinstance(mandate, Mandate):
        raise TypeError("mandate must be a Mandate")
    threshold = _decimal(maximum_correlation_basis_gap)
    if threshold is None or threshold < 0 or threshold > 1:
        raise ValueError("maximum_correlation_basis_gap must be in [0, 1]")

    valuation = evaluate_scenario_outcomes(
        scenario_set=scenario_set,
        portfolio=portfolio,
        candidate=candidate,
        tail_loss_threshold=mandate.client.protection.tail_loss_threshold,
    )
    proxy_weights = _proxy_weights(candidate)
    gross_notionals = tuple(_reference_notional(candidate, leg) for leg in candidate.legs)
    gross_total = sum(gross_notionals, Decimal("0"))
    max_participation = mandate.client.liquidity.max_market_participation
    max_days = Decimal(mandate.client.liquidity.max_unwind_trading_days)
    budget = mandate.client.cost.max_all_in_premium_fraction
    net_premium = valuation.all_in_hedge_cost - candidate.estimated_execution_cost
    outcomes: list[CandidateStressOutcome] = []

    for scenario, valued in zip(scenario_set.scenarios, valuation.outcomes):
        proxy_return = sum(
            (
                weight * scenario.terminal_return(symbol)
                for symbol, weight in proxy_weights.items()
            ),
            Decimal("0"),
        )
        basis_gap = valued.portfolio_return - proxy_return
        absolute_gap = abs(basis_gap)

        stressed_execution = sum(
            (
                candidate.estimated_execution_cost
                * notional
                / gross_total
                * _path_multiplier(
                    scenario,
                    leg.underlying.value,
                    "bid_ask_spread_multipliers",
                    use_minimum=False,
                )
                for leg, notional in zip(candidate.legs, gross_notionals)
            ),
            Decimal("0"),
        )
        stressed_all_in = net_premium + stressed_execution
        stressed_fraction = stressed_all_in / portfolio.total_market_value

        unwind_days: list[Decimal] = []
        liquidity_inputs_valid = True
        for leg in candidate.legs:
            normal_volume = _decimal(
                leg.liquidity_attributes.get("normal_daily_volume")
            )
            volume_multiplier = _path_multiplier(
                scenario,
                leg.underlying.value,
                "market_volume_multipliers",
                use_minimum=True,
            )
            if normal_volume is None or normal_volume <= 0:
                liquidity_inputs_valid = False
                continue
            unwind_days.append(
                Decimal(leg.quantity)
                / (normal_volume * volume_multiplier * max_participation)
            )
        stressed_unwind = max(unwind_days, default=Decimal("Infinity"))
        liquidity_pass = liquidity_inputs_valid and stressed_unwind <= max_days
        cost_pass = stressed_fraction <= budget
        correlation_pass = absolute_gap <= threshold
        incremental_cost = stressed_execution - candidate.estimated_execution_cost
        stressed_hedged_return = (
            valued.hedged_return - incremental_cost / portfolio.total_market_value
        )
        passed = correlation_pass and liquidity_pass and cost_pass
        outcomes.append(
            CandidateStressOutcome(
                scenario_id=scenario.scenario_id,
                scenario_name=scenario.name,
                portfolio_return=valued.portfolio_return,
                hedge_proxy_return=proxy_return,
                correlation_basis_gap=basis_gap,
                absolute_correlation_basis_gap=absolute_gap,
                correlation_pass=correlation_pass,
                baseline_execution_cost=candidate.estimated_execution_cost,
                stressed_execution_cost=stressed_execution,
                stressed_all_in_cost=stressed_all_in,
                stressed_all_in_cost_fraction=stressed_fraction,
                cost_budget_pass=cost_pass,
                stressed_unwind_days=stressed_unwind,
                liquidity_inputs_valid=liquidity_inputs_valid,
                liquidity_pass=liquidity_pass,
                baseline_hedged_return=valued.hedged_return,
                stressed_hedged_return=stressed_hedged_return,
                return_improvement=stressed_hedged_return - valued.portfolio_return,
                passed=passed,
            )
        )

    restrictions: list[str] = []
    failed_basis = [item.scenario_id for item in outcomes if not item.correlation_pass]
    failed_liquidity = [item.scenario_id for item in outcomes if not item.liquidity_pass]
    failed_cost = [item.scenario_id for item in outcomes if not item.cost_budget_pass]
    if failed_basis:
        restrictions.append(
            "Do not represent the hedge as a portfolio floor; correlation-basis "
            "tolerance is breached in: " + ", ".join(failed_basis)
        )
    if failed_liquidity:
        restrictions.append(
            "Do not assume a three-day full unwind in: " + ", ".join(failed_liquidity)
        )
    if failed_cost:
        restrictions.append(
            "Reprice, resize or reserve before quoting under stressed spreads in: "
            + ", ".join(failed_cost)
        )
    return CandidateStressEvaluation(
        scenario_set_id=scenario_set.scenario_set_id,
        scenario_set_version=scenario_set.version,
        candidate_id=candidate.candidate_id,
        portfolio_id=portfolio.portfolio_id,
        maximum_correlation_basis_gap=threshold,
        outcomes=tuple(outcomes),
        passed=all(item.passed for item in outcomes),
        usage_restrictions=tuple(restrictions),
    )


__all__ = [
    "CandidateStressEvaluation",
    "CandidateStressOutcome",
    "evaluate_candidate_stresses",
]
