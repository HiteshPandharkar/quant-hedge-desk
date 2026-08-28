"""Sequential state orchestration for candidate rebalancing stress paths."""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Any, Mapping, Sequence

from quant_hedge_desk.domain.calculations.payoff import (
    future_terminal_payoff,
    option_terminal_payoff,
)
from quant_hedge_desk.domain.enums import RebalanceTriggerType
from quant_hedge_desk.domain.models.derivative_legs import FutureLeg, VanillaOptionLeg
from quant_hedge_desk.domain.models.mandate import Mandate
from quant_hedge_desk.domain.models.portfolio import Portfolio
from quant_hedge_desk.domain.models.rebalancing import (
    CashLedger,
    PositionState,
    RebalanceEvent,
    RebalancingStressPolicy,
)
from quant_hedge_desk.domain.models.scenario_contracts import ScenarioPath
from quant_hedge_desk.hedge_design.candidate_generator import HedgeCandidate
from quant_hedge_desk.hedge_design.rebalancing import (
    contract_id_for_leg,
    execute_rebalance_proposal,
    initial_cash_ledger,
    initial_position,
    propose_rebalance,
)
from quant_hedge_desk.serialization import json_ready


@dataclass(frozen=True, slots=True)
class RebalancingPathResult:
    """Auditable final state and cash-flow result for one scenario path."""

    final_position: PositionState
    cash_ledger: CashLedger
    events: tuple[RebalanceEvent, ...]
    terminal_payoff: Decimal
    hedge_profit: Decimal
    hedged_return: Decimal
    turnover: Decimal
    maximum_delay_trading_days: int
    passed: bool
    failure_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return json_ready(self)


def _step_portfolio_value(
    portfolio: Portfolio,
    step_returns: Mapping[str, Decimal],
    current_value: Decimal,
    holding_values: dict[str, Decimal],
) -> Decimal:
    if "PORTFOLIO" in step_returns:
        return current_value * (Decimal("1") + step_returns["PORTFOLIO"])
    for holding in portfolio.holdings:
        holding_values[holding.symbol] *= Decimal("1") + step_returns[holding.symbol]
    return sum(holding_values.values(), Decimal("0"))


def _terminal_payoff(
    candidate: HedgeCandidate,
    position: PositionState,
    terminal_levels: Mapping[str, Decimal],
) -> Decimal:
    payoff = Decimal("0")
    for leg in candidate.legs:
        quantity = position.quantities[contract_id_for_leg(leg)]
        level = terminal_levels[leg.underlying.value]
        if isinstance(leg, FutureLeg):
            payoff += future_terminal_payoff(
                terminal_level=level,
                entry_level=leg.strike_or_level,
                quantity=quantity,
                contract_multiplier=leg.contract_multiplier,
                direction=leg.direction,
            )
        elif isinstance(leg, VanillaOptionLeg):
            payoff += option_terminal_payoff(
                terminal_level=level,
                strike=leg.strike_or_level,
                quantity=quantity,
                contract_multiplier=leg.contract_multiplier,
                direction=leg.direction,
                option_type=leg.option_type,
            )
        else:  # pragma: no cover - HedgeCandidate enforces this boundary.
            raise TypeError("candidate legs must be futures or vanilla options")
    return payoff


def evaluate_rebalancing_path(
    *,
    scenario: ScenarioPath,
    portfolio: Portfolio,
    candidate: HedgeCandidate,
    mandate: Mandate,
    policy: RebalancingStressPolicy,
    portfolio_horizon_returns: Sequence[float],
    underlying_horizon_returns: Mapping[str, Sequence[float]],
) -> RebalancingPathResult:
    """Apply market moves and required resize attempts in path order."""

    position = initial_position(candidate)
    ledger = initial_cash_ledger(candidate)
    current_portfolio_value = portfolio.total_market_value
    holding_values = {
        holding.symbol: holding.market_value for holding in portfolio.holdings
    }
    current_levels = dict(candidate.initial_levels)
    events: list[RebalanceEvent] = []
    failures: list[str] = []
    pending_trigger: RebalanceTriggerType | None = None
    pending_since: int | None = None

    for index, step in enumerate(scenario.steps):
        current_portfolio_value = _step_portfolio_value(
            portfolio,
            step.asset_returns,
            current_portfolio_value,
            holding_values,
        )
        for symbol in current_levels:
            current_levels[symbol] *= Decimal("1") + step.asset_returns[symbol]

        is_terminal = index == len(scenario.steps) - 1
        if is_terminal:
            continue
        proposal = propose_rebalance(
            candidate,
            position,
            step,
            policy,
            inception_portfolio_value=portfolio.total_market_value,
            current_portfolio_value=current_portfolio_value,
            current_underlying_levels=current_levels,
            is_terminal_step=False,
            required_trigger=pending_trigger,
        )
        if proposal is None:
            if pending_trigger is not None:
                pending_trigger = None
                pending_since = None
            continue

        if pending_trigger is None:
            pending_trigger = proposal.trigger_type
            pending_since = step.step_number
        assert pending_since is not None
        execution = execute_rebalance_proposal(
            candidate,
            position,
            ledger,
            proposal,
            step,
            scenario_id=scenario.scenario_id,
            mandate=mandate,
            portfolio=portfolio,
            current_underlying_levels=current_levels,
            portfolio_horizon_returns=portfolio_horizon_returns,
            underlying_horizon_returns=underlying_horizon_returns,
        )
        delay = step.step_number - pending_since
        event = replace(execution.event, delay_trading_days=delay)
        events.append(event)
        position = execution.position
        ledger = execution.cash_ledger

        if event.failure_reason is not None:
            failures.append(
                f"step {step.step_number}: {event.failure_reason}"
            )
        if delay > 0:
            failures.append(
                f"step {step.step_number}: completed or attempted after {delay} trading days"
            )

        completed = execution.committed and dict(position.quantities) == dict(
            proposal.target_quantities
        )
        if completed:
            pending_trigger = None
            pending_since = None

    maximum_delay = max(
        (event.delay_trading_days for event in events), default=0
    )
    if pending_trigger is not None:
        assert pending_since is not None
        unresolved_delay = scenario.steps[-1].step_number - pending_since
        maximum_delay = max(maximum_delay, unresolved_delay)
        failures.append(
            f"terminal step: UNRESOLVED_REBALANCE after {unresolved_delay} trading days"
        )

    terminal_payoff = _terminal_payoff(candidate, position, current_levels)
    hedge_profit = terminal_payoff + ledger.net_cash_flow
    hedged_return = (
        current_portfolio_value + hedge_profit
    ) / portfolio.total_market_value - Decimal("1")
    return RebalancingPathResult(
        final_position=position,
        cash_ledger=ledger,
        events=tuple(events),
        terminal_payoff=terminal_payoff,
        hedge_profit=hedge_profit,
        hedged_return=hedged_return,
        turnover=sum((event.turnover for event in events), Decimal("0")),
        maximum_delay_trading_days=maximum_delay,
        passed=not failures,
        failure_reasons=tuple(dict.fromkeys(failures)),
    )


__all__ = ["RebalancingPathResult", "evaluate_rebalancing_path"]
